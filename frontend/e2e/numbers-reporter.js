/**
 * Prints, after the run, one line per test with the numbers it asserted (annotations of type
 * "asserted" pushed by the spec's `note()`), so a run's log is also its evidence.
 */
export default class NumbersReporter {
  constructor() {
    this.rows = [];
    this.started = Date.now();
  }

  onTestEnd(test, result) {
    const numbers = test.annotations.filter((a) => a.type === 'asserted').map((a) => a.description);
    const fixme = test.annotations.find((a) => a.type === 'fixme');
    this.rows.push({
      title: test.title,
      status: fixme ? 'fixme' : result.status,
      secs: (result.duration / 1000).toFixed(1),
      numbers: fixme ? `fixme: ${fixme.description || ''}` : numbers.join(' · '),
    });
  }

  onEnd(result) {
    const w = Math.max(...this.rows.map((r) => r.title.length), 10);
    const line = (a, b, c, d) => `${a.padEnd(w)} | ${b.padEnd(7)} | ${c.padStart(6)} | ${d}`;
    console.log('\nFounder-guide smoke — asserted numbers');
    console.log(line('test', 'status', 'secs', 'asserted'));
    console.log(`${'-'.repeat(w)}-+-${'-'.repeat(7)}-+-${'-'.repeat(6)}-+-${'-'.repeat(40)}`);
    for (const r of this.rows) console.log(line(r.title, r.status, r.secs, r.numbers));
    console.log(`total ${((Date.now() - this.started) / 1000).toFixed(1)} s — ${result.status}\n`);
  }

  printsToStdio() {
    return false;
  }
}
