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
  return a + b;
}
