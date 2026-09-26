"""Sequential JSON-line worker; EOF releases the process and model runtimes."""
import json
import sys
import traceback


def main():
    import separation_pool
    separation_pool.enable()
    try:return run_jobs()
    finally:separation_pool.enable(False)


def run_jobs():
    from analyze_song import execute
    for line in sys.stdin:
        job_id=None
        try:
            request=json.loads(line)
            job_id=request['id']
            separation=request.get('separation','mel_bs')
            if separation not in ['mel_bs','mel_roformer','htdemucs']:raise ValueError('Invalid separation')
            execute(request['source'],request['result_file'],True,separation)
        except (Exception,SystemExit):
            traceback.print_exc()
            print('VPL_JOB_DONE '+json.dumps(dict(id=job_id,code=1)),flush=True)
            # Do not reuse a potentially damaged GPU context after failure.
            return 1
        print('VPL_JOB_DONE '+json.dumps(dict(id=job_id,code=0)),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
