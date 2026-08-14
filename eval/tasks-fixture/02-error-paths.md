Audit the error handling in `jobq/worker.py` and `jobq/scheduler.py`.

Report back:

1. Every way a job can fail without a human ever finding out. Trace each one to
   the specific line that swallows it.
2. What happens to `Worker.processed` and to `job.attempts` when a handler
   raises. Say whether those numbers can be trusted for monitoring.
3. Whether `RetryScheduler.max_attempts` is enforced anywhere. If it is not,
   describe what a permanently failing job does to the pool.
4. The interaction between `Worker.run`'s loop and the tasks it spawns. Explain
   what happens to work still in flight when the loop exits.

Do not modify any files. Report your findings in your response.
