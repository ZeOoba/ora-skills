import io, os
D = r"C:\Users\Owner\ora-skills\_staging\2026-08-12_pending-reimport-batch"
main = os.path.join(D, "CODE-SESSION-PROMPT.md")
repl = open(os.path.join(D, "_task3_replacement.md"), encoding="utf-8").read().rstrip() + "\n"
t = open(main, encoding="utf-8").read()
start = t.index("## TASK 3")
end = t.index("## TASK 4")
new = t[:start] + repl + "\n---\n\n" + t[end:]
# also fix the run-order preamble line
new = new.replace(
    "Run the tasks in order. Tasks 1, 2 and 6 are independent of the ruling in Task 3.",
    "Run the tasks in order. Task 3 was ruled on by Gabriel on 2026-08-12 and is now an instruction, not a question.")
open(main, "w", encoding="utf-8", newline="\n").write(new)
print("old len", len(t), "-> new len", len(new))
print("TASK headings now:", [l for l in new.splitlines() if l.startswith("## ")])
