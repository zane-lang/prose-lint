// The view decides the layout.
export const View = () => <p>don't{/* The page wants a header. */}</p>;
const quoted = <p>'quoted {/* The text wants a quote. */} text'</p>;
const nested = (
  <ul title="it's">
    {items.map((item) => <li key={item /* The key knows the order. */}>{item}'s</li>)}
    <br />
  </ul>
); // The list decides the order.
const pick = <T,>(value: T) => value; // The helper wants a type.
const base = <Base extends>don't {/* The base knows the parent. */}</Base>;
const tagged = (
  <div
    // The tag wants an id.
    id="x" /* The class decides the colour. */ className="y"
  >it's</div>
); // The wrapper knows the size.
