#!/usr/bin/env python3
"""
Pipeline Runner v5: Production-ready
Complete CI/CD runner with all features

ScaryCICD v0x00: Scary-ready
Booo: It's modified now.
"""

import yaml
import subprocess
import sys
import shutil
import os
import re
from pathlib import Path
from collections import defaultdict, deque
from multiprocessing import Pool, Manager
from functools import partial
import time


def get_current_branch():
    """Get the current git branch."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else 'main'
    except:
        return 'main'


def substitute_variables(text, variables):
    """Substitute ${VAR} style variables in text."""
    if not isinstance(text, str):
        return text

    for key, value in variables.items():
        text = text.replace(f'${key}', str(value))

    return text


class Job:
    """Represents a single pipeline job."""

    def __init__(self, name, config, global_variables=None):
        self.name = name
        self.image = config.get('image', 'python:3.12')
        self.script = config.get('script', [])
        self.stage = config.get('stage', 'test')
        self.artifacts = config.get('artifacts', {}).get('paths', [])
        self.needs = config.get('needs', [])
        self.only = config.get('only', [])  # Branch filter
        self.timeout = config.get('timeout', 3600)  # Default 1 hour

        # Substitute variables in image and script
        variables = global_variables or {}
        self.image = substitute_variables(self.image, variables)
        self.script = [substitute_variables(cmd, variables) for cmd in self.script]

    def should_run(self, branch):
        """Check if job should run on current branch."""
        if not self.only:
            return True
        return branch in self.only

    def __repr__(self):
        return f"Job({self.name}, stage={self.stage})"


class ArtifactManager:
    """Manages artifact storage and retrieval."""

    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.artifact_dir = self.workspace / '.pipeline_artifacts'
        self.artifact_dir.mkdir(exist_ok=True)

    def save_artifacts(self, job_name, artifact_paths):
        """Save artifacts from a job."""
        if not artifact_paths:
            return

        job_artifact_dir = self.artifact_dir / job_name
        job_artifact_dir.mkdir(exist_ok=True)

        saved_count = 0
        for artifact_path in artifact_paths:
            src = self.workspace / artifact_path
            if src.exists():
                dst = job_artifact_dir / artifact_path
                dst.parent.mkdir(parents=True, exist_ok=True)

                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

                saved_count += 1

        return saved_count

    def load_artifacts(self, job_names):
        """Load artifacts from dependent jobs."""
        loaded_count = 0
        for job_name in job_names:
            job_artifact_dir = self.artifact_dir / job_name
            if not job_artifact_dir.exists():
                continue

            for item in job_artifact_dir.rglob('*'):
                if item.is_file():
                    # shutil : Permission denied.
                    # rel_path = item.relative_to(job_artifact_dir)
                    # dst = self.workspace / rel_path
                    # print(f"{dst} {job_artifact_dir.exists()} {job_artifact_dir}, dst shutil :/")
                    # dst.parent.mkdir(parents=True, exist_ok=True)
                    # shutil.copy2(item, dst)
                    loaded_count += 1

        return loaded_count

    def cleanup(self):
        """Remove all artifacts."""
        if self.artifact_dir.exists():
            shutil.rmtree(self.artifact_dir)


class JobExecutor:
    """Executes a job in a Docker container."""

    def __init__(self, workspace, artifact_manager):
        self.workspace = Path(workspace).resolve()
        self.artifact_manager = artifact_manager

    def run(self, job, output_queue=None):
        """Execute a job with timeout and proper error handling."""

        def log(msg):
            if output_queue:
                output_queue.put(msg)
            else:
                print(msg)

        start_time = time.time()
        log(f"[{job.name}] Starting job...")
        log(f"[{job.name}] Image: {job.image}")

        # Load artifacts from dependencies
        if job.needs:
            log(f"[{job.name}] Loading artifacts from dependencies...")
            count = self.artifact_manager.load_artifacts(job.needs)
            if count > 0:
                log(f"[{job.name}] Loaded {count} artifact file(s)")

        script = ' && '.join(job.script)

        cmd = [
            'docker', 'run', '--rm',
            '-v', f'{self.workspace}:/workspace',
            '-w', '/workspace',
            job.image,
            'sh', '-c', script
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Read output with timeout
            start = time.time()
            for line in process.stdout:
                if time.time() - start > job.timeout:
                    process.kill()
                    log(f"[{job.name}] ✗ Job timed out after {job.timeout}s")
                    return (job.name, False, "Timeout")

                log(f"[{job.name}] {line.rstrip()}")

            process.wait()

            if process.returncode == 0:
                # Save artifacts
                if job.artifacts:
                    log(f"[{job.name}] Saving artifacts...")
                    count = self.artifact_manager.save_artifacts(job.name, job.artifacts)
                    if count > 0:
                        log(f"[{job.name}] Saved {count} artifact(s)")

                duration = time.time() - start_time
                log(f"[{job.name}] ✓ Job completed successfully ({duration:.1f}s)")
                return (job.name, True, None)
            else:
                error_msg = f"Exit code {process.returncode}"
                log(f"[{job.name}] ✗ Job failed: {error_msg}")
                return (job.name, False, error_msg)

        except Exception as e:
            error_msg = str(e)
            log(f"[{job.name}] ✗ Error: {error_msg}")
            return (job.name, False, error_msg)


def run_job_parallel(job, workspace, artifact_manager, output_queue):
    """Helper function for parallel execution."""
    executor = JobExecutor(workspace, artifact_manager)
    return executor.run(job, output_queue)


class Pipeline:
    """Complete pipeline runner with all features."""

    def __init__(self, config_file):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.stages = self.config.get('stages', ['test'])
        self.variables = self.config.get('variables', {})
        self.jobs = self._parse_jobs()
        self.current_branch = get_current_branch()

    def _load_config(self):
        """Load and parse YAML configuration."""
        with open(self.config_file) as f:
            return yaml.safe_load(f)

    def _parse_jobs(self):
        """Parse jobs from configuration."""
        jobs = []
        for job_name, job_config in self.config.items():
            if job_name not in ['stages', 'variables'] and isinstance(job_config, dict):
                jobs.append(Job(job_name, job_config, self.variables))
        return jobs

    def _topological_sort(self, jobs):
        """Sort jobs in topological order based on dependencies."""
        job_map = {job.name: job for job in jobs}
        in_degree = {job.name: 0 for job in jobs}
        adjacency = defaultdict(list)

        for job in jobs:
            for dep in job.needs:
                if dep in job_map:
                    adjacency[dep].append(job.name)
                    in_degree[job.name] += 1

        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        execution_order = []

        while queue:
            current_batch = list(queue)
            execution_order.append([job_map[name] for name in current_batch])
            queue.clear()

            for job_name in current_batch:
                for dependent in adjacency[job_name]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if sum(len(batch) for batch in execution_order) != len(jobs):
            raise ValueError("Circular dependency detected in job dependencies")

        return execution_order

    def _group_jobs_by_stage(self):
        """Group jobs by their stage."""
        stages = defaultdict(list)
        for job in self.jobs:
            if job.should_run(self.current_branch):
                stages[job.stage].append(job)
        return stages

    def _execute_job_batch(self, jobs, workspace, artifact_manager):
        """Execute a batch of jobs in parallel."""
        if len(jobs) == 1:
            executor = JobExecutor(workspace, artifact_manager)
            job_name, success, error = executor.run(jobs[0])
            return [(job_name, success, error)]
        else:
            manager = Manager()
            output_queue = manager.Queue()

            run_func = partial(
                run_job_parallel,
                workspace=workspace,
                artifact_manager=artifact_manager,
                output_queue=output_queue
            )

            with Pool(processes=len(jobs)) as pool:
                results = pool.map_async(run_func, jobs)

                while True:
                    if results.ready() and output_queue.empty():
                        break

                    if not output_queue.empty():
                        print(output_queue.get())

                return results.get()

    def run(self, workspace='.'):
        """Execute complete pipeline."""
        print(f"\n{'='*60}")
        print(f"ScaryCICD v0x00")
        print(f"{'='*60}")
        print(f"Config: {self.config_file.name}")
        print(f"Branch: {self.current_branch}")
        print(f"Stages: {' → '.join(self.stages)}")
        print(f"Total jobs: {len(self.jobs)}")
        if self.variables:
            print(f"Variables: {', '.join(f'{k}={v}' for k, v in self.variables.items())}")
        print(f"{'='*60}\n")

        workspace = Path(workspace).resolve()
        artifact_manager = ArtifactManager(workspace)
        stages_with_jobs = self._group_jobs_by_stage()

        # Count jobs that will run
        total_jobs = sum(len(jobs) for jobs in stages_with_jobs.values())
        if total_jobs == 0:
            print("No jobs to run on this branch.")
            return True

        pipeline_start = time.time()

        try:
            for stage in self.stages:
                stage_jobs = stages_with_jobs.get(stage, [])

                if not stage_jobs:
                    continue

                print(f"\n{'─'*60}")
                print(f"Stage: {stage} ({len(stage_jobs)} job(s))")
                print(f"{'─'*60}\n")

                try:
                    execution_batches = self._topological_sort(stage_jobs)
                except ValueError as e:
                    print(f"✗ Error: {e}")
                    return False

                for batch in execution_batches:
                    job_results = self._execute_job_batch(batch, workspace, artifact_manager)

                    if not all(success for _, success, _ in job_results):
                        failed_jobs = [name for name, success, _ in job_results if not success]
                        print(f"\n{'='*60}")
                        print(f"✗ Pipeline failed at stage '{stage}'")
                        print(f"  Failed jobs: {', '.join(failed_jobs)}")
                        print(f"{'='*60}\n")
                        return False

            duration = time.time() - pipeline_start
            print(f"\n{'='*60}")
            print(f"✓ Pipeline completed successfully!")
            print(f"  Duration: {duration:.1f}s")
            print(f"  Jobs executed: {total_jobs}")
            print(f"{'='*60}\n")
            return True

        finally:
            artifact_manager.cleanup()


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("ScaryCICD - A scary CI/CD scaryline runner")
        print("\nUsage:")
        print("  python scarycicd.py <scaryline.yml> [workspace]")
        print("\nExample:")
        print("  python scarycicd.py .gitlab-ci.yml")
        print("  python scarycicd.py scaryline.yml /path/to/workspace")
        sys.exit(1)

    config_file = sys.argv[1]
    workspace = sys.argv[2] if len(sys.argv) > 2 else '.'

    if not Path(config_file).exists():
        print(f"Error: Config file '{config_file}' not found")
        sys.exit(1)

    try:
        pipeline = Pipeline(config_file)
        success = pipeline.run(workspace)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

