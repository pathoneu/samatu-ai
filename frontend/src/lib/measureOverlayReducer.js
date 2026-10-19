// Pure draft-state reducer for the measurement overlay. Draft holds the in-progress
// polyline/polygon vertices in PDF-point space. The active tool is NOT part of state;
// it is passed in via action.tool for the 'click' and 'finish' cases.
function dist(a, b) { return Math.hypot(b.x - a.x, b.y - a.y); }

export function draftReducer(state, action) {
  switch (action.type) {
    case 'click': {
      const { tool } = action;
      if (tool === 'area' && state.points.length >= 3 && action.closeTolerance != null
          && dist(action.point, state.points[0]) <= action.closeTolerance) {
        return { points: state.points, committed: true };          // close polygon, don't append
      }
      return { points: [...state.points, action.point], committed: false };
    }
    case 'finish': {
      const min = action.tool === 'area' ? 3 : 2;
      return { points: state.points, committed: state.points.length >= min };
    }
    // several points at once — an arc segment (Pathon v3 W5-A A11)
    case 'extend': return { points: [...state.points, ...(action.points || [])], committed: false };
    case 'undo':  return { points: state.points.slice(0, -1), committed: false };
    case 'reset': return { points: [], committed: false };
    default:      return state;
  }
}
