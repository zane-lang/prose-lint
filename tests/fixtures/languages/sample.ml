(* The triple says it is x86_64. *)
let s = "(* The text says so. *)"
let c = '"'
let f 'a x = x (* A plain comment that lists the build steps. *)

(** [parse_date s] reads a date.

    The [s] argument tells the parser what it is.
    {[
      let thing = "the thing says hi"
    ]}
    @param s the text says so *)
let parse_date s = s

(* Outer (* nested comments hide "*)" in strings *) and the value decides. *)
let q = {id|(* The value knows nothing. *)|id}
