#!/usr/bin/env python3
#
# Copyright 2022 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Paul Scheffler <paulsc@iis.ee.ethz.ch>
# Nils Wistoff <nwistoff@iis.ee.ethz.ch>

import os
import sys
import time
import requests
import urllib.parse
import json

def main(sha: str, token: str, domain: str, repo: str, api_version: str,
         retry_count: int, retry_period: int, poll_count: int, poll_period: int, artifact_in: str, artifact_out: str):
    # Derive pipeline URL
    pipelines = f'https://{domain}/api/{api_version}/projects/{urllib.parse.quote_plus(repo)}/pipelines'

    # Wait for pipeline to spawn
    for i in range(1, retry_count+1):
        response = requests.get(pipelines, headers={'PRIVATE-TOKEN': token}).json()
        if 'error' in response:
            print(f'Error: \'{response["error"]}\' error response received to Gitlab API request to get pipeline status. {response["error_description"]} Gitlab API scope: \'{response["scope"]}\'')
            return 4
        try:
            next(p for p in response if p['sha'] == sha)
            break
        except StopIteration:
            print(f'[{i*retry_period}s] No pipeline yet for SHA {sha}')
            time.sleep(retry_period)
    else:
        print(f'[{retry_count*retry_period}s] Pipeline spawn timeout')
        return 2

    # Wait for pipeline to complete
    for i in range(1, poll_count+1):
        response = requests.get(pipelines, headers={'PRIVATE-TOKEN': token}).json()
        if 'error' in response:
            print(f'Error: \'{response["error"]}\' error response received to Gitlab API request to get pipeline status. {response["error_description"]} Gitlab API scope: \'{response["scope"]}\'')
            return 4
        pipeline = next(p for p in response if p['sha'] == sha)
        if pipeline['status'] == 'success':
            print(f'[{i*poll_period}s] Pipeline success! See {pipeline["web_url"]}')

            if artifact_in is not None:
                # get pipeline id
                pid = pipeline['id']

                # get pipeline jobs
                jobs = f'https://{domain}/api/{api_version}/projects/{urllib.parse.quote_plus(repo)}/pipelines/{pid}/jobs'
                response = requests.get(jobs, headers={'PRIVATE-TOKEN': token}).json()
                if 'error' in response:
                    print(f'Error: \'{response["error"]}\' error response received to Gitlab API request to get pipeline status. {response["error_description"]} Gitlab API scope: \'{response["scope"]}\'')
                    return 4
                
                # select testset job & job ID
                job = next(p for p in response if p['name'] == 'testset')
                jid = job['id']

                # get job artifacts (does not fail gracefully right now)
                artifacts = f'https://{domain}/api/{api_version}/projects/{urllib.parse.quote_plus(repo)}/jobs/{jid}/artifacts/{artifact_in}'
                perf = requests.get(artifacts, headers={'PRIVATE-TOKEN': token}).json()
                try:
                    os.makedirs(os.path.split(artifact_out)[0])
                except FileExistsError:
                    pass
                with open(f'{artifact_out}', 'w', encoding='utf-8') as f:
                    json.dump(perf, f, ensure_ascii=False, indent=4)
                absartifact = os.path.abspath(artifact_out)
                print(f'Saved artifact in {absartifact}!')

            return 0
        elif pipeline['status'] in ('failed', 'canceled', 'skipped'):
            print(f'[{i*poll_period}s] Pipeline failure! See {pipeline["web_url"]}')
            return 1
        print(f'[{i*poll_period}s] Pipeline status: {pipeline["status"]}')
        time.sleep(poll_period)
    else:
        print(f'[{poll_count*poll_period}s] Pipeline completion timeout! See {pipeline["web_url"]}')
        return 3


if __name__ == '__main__':
    sys.exit(main(*(int(a) if a.isdigit() else a for a in sys.argv[1:])))
