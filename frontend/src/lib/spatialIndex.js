/**
 * RBush-backed spatial index for overlay markers and polygons.
 *
 * The plain rbush API works on bbox-only entries — we extend each entry
 * with a domain id + kind so click hit-tests return the renderable
 * (count_marker | polygon_vertex | polygon_body), not just a rectangle.
 */
import RBush from 'rbush';

export class OverlayIndex {
  constructor() {
    this.tree = new RBush();
  }

  insert(item) {
    // item: { id, kind, minX, minY, maxX, maxY, payload }
    this.tree.insert(item);
  }

  bulkLoad(items) {
    this.tree.load(items);
  }

  hit(x, y) {
    return this.tree.search({
      minX: x - 1, minY: y - 1, maxX: x + 1, maxY: y + 1,
    });
  }

  inViewport(minX, minY, maxX, maxY) {
    return this.tree.search({ minX, minY, maxX, maxY });
  }

  remove(id) {
    const all = this.tree.all();
    this.tree.clear();
    this.tree.load(all.filter(i => i.id !== id));
  }

  clear() {
    this.tree.clear();
  }
}
