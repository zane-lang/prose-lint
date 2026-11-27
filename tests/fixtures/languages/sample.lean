/-! The module says what it is. -/

/-- The lemma decides the bound. -/
theorem t (h h' : Nat) : h = h := rfl -- The proof knows the answer.

def s : String := "-- The text says so."
def r : String := r#"/- The value knows. -/"#
def c : Char := '-'

/- Outer comment.
  /- The nested note wants a name. -/
  The parser reads each field. -/
def «"» : Nat := 1
-- The proof knows the answer.
