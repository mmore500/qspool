# Usage

You need to submit more slurm scripts than fit on the queue at once.
```bash
tree .
.
├── slurmscript0.slurm.sh
├── slurmscript1.slurm.sh
├── slurmscript2.slurm.sh
├── slurmscript3.slurm.sh
├── slurmscript4.slurm.sh
├── slurmscript5.slurm.sh
├── slurmscript6.slurm.sh
├── slurmscript7.slurm.sh
├── slurmscript8.slurm.sh
...
```

The `qspool` script will feed your job scripts onto the queue as space becomes available.
```bash
qspool *.slurm.sh
```

The `qspool` script creates a slurm job that submits your job scripts.
When queue capacity fills, this `qspool` job will schedule a follow-up job to submit any remaining job scripts.
This process continues until all job scripts have been submitted.

```
usage: qspool [-h] [--payload-job-script-paths-infile PAYLOAD_JOB_SCRIPT_PATHS_INFILE] [--job-log-path JOB_LOG_PATH] [--job-script-cc-path JOB_SCRIPT_CC_PATH]
                 [--queue-capacity QUEUE_CAPACITY] [--qspool-job_title QSPOOL_JOB_TITLE]
                 [payload_job_script_paths ...]

positional arguments:
  payload_job_script_paths
                        What scripts to spool onto slurm queue? (default: None)

options:
  -h, --help            show this help message and exit
  --payload-job-script-paths-infile PAYLOAD_JOB_SCRIPT_PATHS_INFILE
                        Where to read script paths to spool onto slurm queue? (default: <_io.TextIOWrapper name='<stdin>' mode='r' encoding='utf-8'>)
  --job-log-path JOB_LOG_PATH
                        Where should logs for qspool jobs be written? (default: ~/slurm_job_log/)
  --job-script-cc-path JOB_SCRIPT_CC_PATH
                        Where should copies of submitted job scripts be kept? (default: ~/slurm_job_script_cc/)
  --queue-capacity QUEUE_CAPACITY
                        How many jobs can be running or waiting at once? (default: 1000)
  --qspool-job_title QSPOOL_JOB_TITLE
                        What title should be included in spool job name? (default: spooler)
```

# Installation

no installation:
```bash
python3 "$(tmpfile="$(mktemp)"; curl -s https://raw.githubusercontent.com/mmore500/qspool/v0.2.0/qspool.py > "${tmpfile}"; echo "${tmpfile}")" [ARGS]
```

pip installation:
```bash
python3 -m pip install qspool
python3 -m qspool [ARGS]
```

`qspool` has zero dependencies, so no setup or maintenance is required to use it.
Compatible all the way back to Python 3.6, so it will work on your cluster's ancient Python install.

# How it Works

```
qspool
  * read contents of target slurm scripts
  * instantiate spooler job script w/ target slurm scripts embedded
  * submit spooler job script to slurm queue
```

⬇️ ⬇️ ⬇️

```
spooler job 1
  * submit embedded target slurm scripts one by one until queue is almost full
  * instantiate spooler job script w/ remaining target slurm scripts embedded
  * submit spooler job script to slurm queue
```

⬇️ ⬇️ ⬇️

```
spooler job 2
  * submit embedded target slurm scripts one by one until queue is almost full
  * instantiate spooler job script w/ remaining target slurm scripts embedded
  * submit spooler job script to slurm queue
```

...

```
spooler job n
  * submit embedded target slurm scripts one by one
  * no embedded target slurm scripts remain
  * exit
```
