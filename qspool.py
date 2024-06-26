#!/usr/bin/env python3
#SBATCH --job-name="{{ qspool::qspool_job_name }}"  # Job name
#SBATCH --mail-type=FAIL                          # Mail events
#SBATCH --ntasks=1                       # Run on a single CPU
#SBATCH --mem=1gb                        # Job memory request
#SBATCH --time=04:00:00                  # Time limit hrs:min:sec
#SBATCH --output="{{ qspool::job_log_path }}/a=log+{{ qspool::qspool_job_name }}+slurm_job_id=%j+ext=.txt"
#SBATCH --requeue  # Job may be requeued after node failure

__version__ = "0.5.0"
__author__ = "Matthew Andres Moreno"

import argparse
from base64 import b64encode, b64decode
import inspect
import itertools as it
import json
import logging
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import typing
import zlib

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="| %Y-%m-%d %H:%M:%S",
)


def is_this_script_instantiated() -> bool:
    return not "{{ qspool::instantiate_with_empty }}"


def instantiation_or_none(
    field: str,
    apply: typing.Callable = lambda x: x,
) -> typing.Optional[typing.Any]:
    if is_this_script_instantiated():
        return apply(field)
    else:
        return None


payload_job_script_contents_list = instantiation_or_none(
    r"""{{ qspool::payload_job_script_contents_list_json }}""",
    apply=lambda x: json.loads(zlib.decompress(b64decode(x)), strict=False),
)
job_script_cc_path = instantiation_or_none(
    "{{ qspool::job_script_cc_path }}",
)
job_log_path = instantiation_or_none(
    "{{ qspool::job_log_path }}",
)
queue_capacity = instantiation_or_none(
    "{{ qspool::queue_capacity }}", apply=int
)
qspooler_chain_depth = instantiation_or_none(
    "{{ qspool::qspooler_chain_depth }}", apply=int
)
qspooler_job_title = instantiation_or_none(
    "{{ qspool::qspooler_job_title }}",
)
this_script_template = instantiation_or_none(
    r""" {{ qspool::this_script_template }} """,  # spaces prevent first/last "
    apply=lambda x: json.loads(x, strict=False),
)


def run_until_success(command: typing.List[str]) -> typing.Any:
    logging.info(f"executing command {command}")
    for attempt in it.count(1):
        try:
            res = subprocess.run(
                command,
                check=True,
                encoding="ascii",
                env=os.environ.copy(),
                shell=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            if res.stderr:
                logging.info(f"command {command} wrote to stderr")
                logging.info(
                    "\n" + re.sub("^", "| | ", res.stderr, flags=re.MULTILINE)
                )
            return res
        except subprocess.CalledProcessError as e:
            logging.warning(f"command {command} raised {e}")
            logging.info(
                f"{command} attempt {attempt} failed; retrying in 5 seconds"
            )
            time.sleep(5)


def check_queue_size() -> int:
    queue_size = run_until_success("squeue -u ${USER}").stdout.count("\n") - 1
    logging.info(f"queue size {queue_size} detected")
    return queue_size


def sbatch(job_script_path: str, job_script_cc_path: str) -> None:
    run_result = run_until_success(f"sbatch {job_script_path}")
    logging.info(f"sbatch stdout was {run_result.stdout}")
    (slurm_job_id,) = re.search(
        "^[^0-9]*([0-9]+)[^0-9]*$", run_result.stdout
    ).groups()
    logging.info(
        f"sbatch script {job_script_path} queued as job {slurm_job_id}"
    )

    # copy to directory with scripts
    pathlib.Path(job_script_cc_path).mkdir(parents=True, exist_ok=True)
    job_script_cc_file_path = (
        f"{job_script_cc_path}/job_id={slurm_job_id}+ext=.slurm.sh"
    )
    shutil.copy(job_script_path, job_script_cc_file_path)
    logging.info(
        f"cc'ed sbatch script {job_script_path} to {job_script_cc_file_path}"
    )
    os.chmod(job_script_cc_file_path, 0o775)


def get_this_script_source():
    # adapted from https://stackoverflow.com/a/34492072
    return inspect.getsource(inspect.getmodule(inspect.currentframe()))


def is_queue_capacity_available(queue_capacity: int) -> bool:
    race_condition_safety_margin = 100
    queue_size = check_queue_size()

    res = queue_size < queue_capacity - race_condition_safety_margin

    if not res:
        logging.info(f"queue capacity unavailable queue_size={queue_size}")
    return res


def is_at_least_1hr_job_time_remaining(start_time) -> bool:
    cur_time=time.time()

    # assumes 4 hour job time
    available_job_seconds = 4 * 60 * 60
    hour_num_seconds = 60 * 60
    elapsed_seconds = cur_time - start_time

    threshold_seconds = available_job_seconds - hour_num_seconds

    logging.info("testing job time remaining")
    logging.info(f"start_time={start_time}")
    logging.info(f"cur_time={cur_time}")
    logging.info(f"elapsed_seconds={elapsed_seconds}")
    logging.info(f"threshold_seconds={threshold_seconds}")

    res = elapsed_seconds < threshold_seconds

    if not res:
        logging.info(
            f"insufficient job time remaining elapsed_seconds={elapsed_seconds}"
        )
    else:
        logging.info(
            f"sufficient job time remaining elapsed_seconds={elapsed_seconds}"
        )
    return res


def make_qspool_job_name(
    qspooler_job_title: str,
    payload_job_scripts_list: typing.List[str],
    qspooler_chain_depth: int,
) -> str:
    return f"""what=qspooler+depth={
        qspooler_chain_depth
    }+payload_size={
        len(payload_job_scripts_list)
    }+title={
        qspooler_job_title
    }"""


if __name__ == "__main__":
    logging.info(f"__version__={__version__}")
    start_time = time.time()
    logging.info(f"start_time={start_time}")
    logging.info(f"hostname={socket.gethostname()}")

    if not is_this_script_instantiated():
        logging.info("running kickoff routine...")
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        parser.add_argument(
            "payload_job_script_paths",
            help="What scripts to spool onto slurm queue?",
            nargs="*",
        )
        parser.add_argument(
            "--payload-job-script-paths-infile",
            default=sys.stdin,
            help="Where to read script paths to spool onto slurm queue?",
            type=argparse.FileType("r"),
        )
        parser.add_argument(
            "--job-log-path",
            default="~/joblog/",
            help="Where should logs for qspool jobs be written?",
            type=str,
        )
        parser.add_argument(
            "--job-script-cc-path",
            default="~/jobscript/",
            help="Where should copies of submitted job scripts be kept?",
            type=str,
        )
        parser.add_argument(
            "--queue-capacity",
            default=1000,
            help="How many jobs can be running or waiting at once?",
            type=int,
        )
        parser.add_argument(
            "--qspooler-job-title",
            default="none",
            help="What title should be included in qspooler job names?",
            type=str,
        )
        args = parser.parse_args()

        payload_job_script_paths = (
            [
                word
                for line in args.payload_job_script_paths_infile
                for word in line.split()
            ]
            if not sys.stdin.isatty()
            else []
        ) + args.payload_job_script_paths

        if not payload_job_script_paths:
            logging.warning("no payload script paths provided")
        else:
            logging.info(
                f"{len(payload_job_script_paths)} payload script paths provided"
            )
            logging.info(
                f"{len(set(payload_job_script_paths))} distinct payload script "
                "paths provided"
            )

        payload_job_script_contents_list = []
        for payload_job_script_path in payload_job_script_paths:
            with open(payload_job_script_path, "r") as payload_job_script_file:
                payload_job_script_contents_list.append(
                    "".join(payload_job_script_file.readlines())
                )
                if not payload_job_script_contents_list[-1]:
                    logging.warning(f"{payload_job_script_path} was empty")

        job_log_path = os.path.expanduser(args.job_log_path)
        job_script_cc_path = os.path.expanduser(args.job_script_cc_path)
        queue_capacity = args.queue_capacity
        qspooler_chain_depth = 0
        qspooler_job_title = args.qspooler_job_title

    logging.info("running configuration setup and logging routine...")

    assert job_log_path is not None
    logging.info(f"job_log_path={job_log_path}")
    pathlib.Path(job_log_path).mkdir(parents=True, exist_ok=True)

    assert job_script_cc_path is not None
    logging.info(f"job_script_cc_path={job_script_cc_path}")
    pathlib.Path(job_script_cc_path).mkdir(parents=True, exist_ok=True)

    assert queue_capacity is not None
    logging.info(f"queue_capacity={queue_capacity}")

    assert qspooler_chain_depth is not None
    logging.info(f"qspooler_chain_depth={qspooler_chain_depth}")

    assert qspooler_job_title is not None
    logging.info(f"qspooler_job_title={qspooler_job_title}")

    assert payload_job_script_contents_list is not None
    logging.info(
        f"""{
            len(payload_job_script_contents_list)
        } jobs in payload_job_script_contents_list"""
    )
    logging.info(
        f"""{
            len(set(payload_job_script_contents_list))
        } distinct jobs in payload_job_script_contents_list"""
    )

    if this_script_template is None:
        this_script_template = get_this_script_source()

    if is_this_script_instantiated():
        logging.info("running submission routine...")
        while (
            payload_job_script_contents_list
            and is_queue_capacity_available(queue_capacity)
            and is_at_least_1hr_job_time_remaining(start_time)
        ):
            with tempfile.NamedTemporaryFile(mode="w+") as script_file:
                logging.info(f"created payload job script {script_file.name}")
                script_file.write(payload_job_script_contents_list.pop())
                script_file.file.close()
                os.chmod(script_file.name, 0o775)

                logging.info(
                    f"""{
                        os.path.getsize(script_file.name)
                    } bytes written to job script {
                        script_file.name
                    }"""
                )

                sbatch(script_file.name, job_script_cc_path)
                logging.info(
                    f"""{
                        len(payload_job_script_contents_list)
                    } payload jobs remaining"""
                )

    if payload_job_script_contents_list:
        logging.info(
            f"""{
                len(payload_job_script_contents_list)
            } payload jobs remaining; creating qspool continuation job"""
        )
        logging.info(
            f"""{
                len(set(payload_job_script_contents_list))
            } distinct jobs in payload_job_script_contents_list"""
        )
        continuation_job_script_contents = (
            this_script_template.replace(
                "{{ qspool::job_log_path }}", job_log_path, 2
            )
            .replace("{{ qspool::job_script_cc_path }}", job_script_cc_path, 1)
            .replace("{{ qspool::instantiate_with_empty }}", "", 1)
            .replace(
                "{{ qspool::payload_job_script_contents_list_json }}",
                b64encode(
                    zlib.compress(
                        json.dumps(payload_job_script_contents_list).encode(
                            "utf-8"
                        )
                    )
                ).decode("ascii"),
                1,
            )
            .replace(
                "{{ qspool::qspool_job_name }}",
                make_qspool_job_name(
                    qspooler_job_title,
                    payload_job_script_contents_list,
                    qspooler_chain_depth + 1
                ),
                2,
            )
            .replace("{{ qspool::queue_capacity }}", str(queue_capacity), 1)
            .replace("{{ qspool::qspooler_job_title }}", qspooler_job_title, 1)
            .replace(
                "{{ qspool::qspooler_chain_depth }}",
                str(qspooler_chain_depth + 1),
                1,
            )
            .replace(
                "{{ qspool::this_script_template }}",
                json.dumps(this_script_template),
                1,
            )
        )
        with tempfile.NamedTemporaryFile(
            mode="w+",
        ) as continuation_job_script_file:
            logging.info("running continuation routine...")
            logging.info(
                f"""created continuation job script {
                    continuation_job_script_file.name
                } with {len(continuation_job_script_contents.splitlines())} lines"""
            )

            continuation_job_script_file.write(
                continuation_job_script_contents.strip()
            )
            continuation_job_script_file.file.close()
            os.chmod(continuation_job_script_file.name, 0o775)
            logging.info(
                f"""{
                os.path.getsize(continuation_job_script_file.name)
            } bytes written to job script {
                continuation_job_script_file.name
            }"""
            )
            sbatch(continuation_job_script_file.name, job_script_cc_path)
            logging.info("continuation job creation and submisison complete")

    else:
        logging.info(
            "payload job scripts exhausted, completing without continuation"
        )

    logging.info("QSPOOL::SUCCESSFUL_COMPLETION")
