The job queue in `jobq/` occasionally processes the same job more than once.
`python3 verify.py` demonstrates it.

Investigate and report back:

1. The precise interleaving that causes it. Name the two workers, the exact
   lines where they interleave, and why the window opens at all.
2. Why the duplicated job indices come out at the spacing they do, rather than
   uniformly at random.
3. Why `all_jobs_complete` still passes while this is happening.
4. The fix you would apply, as a diff. Explain what your fix guarantees and what
   it does not.

Do not modify any files. Report your findings in your response.
