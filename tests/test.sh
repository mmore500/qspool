#!/bin/bash

set -e

# adapted from https://unix.stackexchange.com/a/504829
err() {
  cd -
  echo "Error occurred:"
  awk 'NR>L-4 && NR<L+4 { printf "%-5d%3s%s\n",NR,(NR==L?">>>":""),$0 }' L=$1 $0
}
trap 'err $LINENO' ERR

cd "$(dirname "${BASH_SOURCE[0]}")"

export PATH=${PATH}:"${PWD}/mock_bin"

echo
echo "# TEST CASE 1 ##########################################################"
rm -rf \
  "/tmp/job_script_cc_path/" \
  "/tmp/touched-by-example1.slurm.sh" \
  "/tmp/touched-by-example2.slurm.sh"

echo assets/example1.slurm.sh | ../qspool.py \
  --job-script-cc-path "/tmp/job_script_cc_path"

cmp --silent \
    "/tmp/job_script_cc_path/job_id=6+ext=.slurm.sh" \
    "assets/example1.slurm.sh"

test -f "/tmp/job_script_cc_path/job_id=698+ext=.slurm.sh"
test -f "/tmp/touched-by-example1.slurm.sh"

echo
echo "# TEST CASE 2 ##########################################################"
rm -rf \
  "/tmp/job_script_cc_path/" \
  "/tmp/touched-by-example1.slurm.sh" \
  "/tmp/touched-by-example2.slurm.sh"

../qspool.py \
  assets/example2.slurm.sh \
  --job-script-cc-path "/tmp/job_script_cc_path"

cmp --silent \
    "/tmp/job_script_cc_path/job_id=8+ext=.slurm.sh" \
    "assets/example2.slurm.sh"

test -f "/tmp/job_script_cc_path/job_id=698+ext=.slurm.sh"
test -f "/tmp/touched-by-example2.slurm.sh"

echo
echo "# TEST CASE 3 ##########################################################"
rm -rf \
  "/tmp/job_script_cc_path/" \
  "/tmp/touched-by-example1.slurm.sh" \
  "/tmp/touched-by-example2.slurm.sh"

echo assets/example1.slurm.sh | ../qspool.py \
  assets/example2.slurm.sh \
  --job-script-cc-path "/tmp/job_script_cc_path"

cmp --silent \
    "/tmp/job_script_cc_path/job_id=6+ext=.slurm.sh" \
    "assets/example1.slurm.sh"
cmp --silent \
    "/tmp/job_script_cc_path/job_id=8+ext=.slurm.sh" \
    "assets/example2.slurm.sh"

test -f "/tmp/job_script_cc_path/job_id=698+ext=.slurm.sh"
test -f "/tmp/touched-by-example1.slurm.sh"
test -f "/tmp/touched-by-example2.slurm.sh"
