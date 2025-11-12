# ScaryCICD v0x00

Uses Python3 and docker as root :smile_cat:.

[GTFObins.docker](https://gtfobins.github.io/gtfobins/docker/)

- Docker stick an interesting program to those who know how to use it...

- Docker has its place in a seperate host.

- It shouldn't be used on a desktop directly but in virtual machine...

here is the output scarycicd.py.

```text
python scarycicd.py scaryline.yml 

============================================================
ScaryCICD v0x00
============================================================
Config: scaryline.yml
Branch: main
Stages: lol0 → lol1 → lol2
Total jobs: 4
============================================================


────────────────────────────────────────────────────────────
Stage: lol0 (2 job(s))
────────────────────────────────────────────────────────────

[scary-lint] Starting job...
[scary-lint] Image: python:3.12
[scary-test] Starting job...
[scary-test] Image: python:3.12
[scary-lint] uid=0(root) gid=0(root) groups=0(root)
[scary-test] uid=0(root) gid=0(root) groups=0(root)
[scary-lint] ✓ Job completed successfully (0.7s)
[scary-test] ✓ Job completed successfully (0.8s)

────────────────────────────────────────────────────────────
Stage: lol1 (1 job(s))
────────────────────────────────────────────────────────────

[scary-package] Starting job...
[scary-package] Image: python:3.12
[scary-package] Loading artifacts from dependencies...
[scary-package] uid=0(root) gid=0(root) groups=0(root)
[scary-package] ✓ Job completed successfully (0.6s)

────────────────────────────────────────────────────────────
Stage: lol2 (1 job(s))
────────────────────────────────────────────────────────────

[scary-app] Starting job...
[scary-app] Image: alpine:latest
[scary-app] Loading artifacts from dependencies...
[scary-app] uid=0(root) gid=0(root) groups=0(root),1(bin),2(daemon),3(sys),4(adm),6(disk),10(wheel),11(floppy),20(dialout),26(tape),27(video)
[scary-app] ✓ Job completed successfully (0.6s)

============================================================
✓ Pipeline completed successfully!
  Duration: 2.0s
  Jobs executed: 4
============================================================
```

###### No program been harmed awhile the tests.
