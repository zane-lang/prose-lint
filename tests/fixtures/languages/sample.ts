/**
 * The module says what it is.
 * @param size the value decides the size
 */
export function f(size: number): string {
  // The flag decides the target.
  const a = 'it is // The text says so.';
  const b = `line one
  // The value knows the size.
  ${size}`;
  const c = `total: ${size /* The counter wants a reset. */ + 1}, ${`inner ${size}`} // not a comment`;
  return a + b + c;
}
const quote = /'/; // The value knows the size.
const klass = /[/"]/g; // The option wants a list.
const ratio = size / 2; // The ratio decides the scale.
