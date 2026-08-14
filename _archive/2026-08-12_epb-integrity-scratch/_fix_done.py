import os, shutil
D = r"C:\Users\Owner\ora-skills\_staging\2026-08-12_pending-reimport-batch"
A = r"C:\Users\Owner\ora-skills\_archive\2026-08-12_epb-integrity-scratch"
main = os.path.join(D, "CODE-SESSION-PROMPT.md")
t = open(main, encoding="utf-8").read()
old = "Task 3 ruled on by Gabriel and the ruling recorded in `event_log.md` (even if the implementation is deferred)"
new = ("Task 3 implemented per the 2026-08-12 ruling \u2014 \u00a71\u2013\u00a72 inlined, \u00a73/\u00a76 verifiably NOT carried over, "
       "all four references rewired, RETIRED.md corrected")
assert old in t, "done-line anchor not found"
t = t.replace(old, new)
open(main, "w", encoding="utf-8", newline="\n").write(t)
print("done-line updated")
for f in ["_task3_replacement.md", "_splice_task3.py", "_fix_done.py"]:
    s = os.path.join(D, f)
    if os.path.exists(s):
        shutil.move(s, os.path.join(A, f))
        print("archived", f)
print("staging dir now:", sorted(os.listdir(D)))
