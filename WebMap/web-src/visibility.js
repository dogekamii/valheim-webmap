export const FOGGED_VISIBILITY_MODE = 'fogged';
export const HYBRID_VISIBILITY_MODE = 'hybrid';
export const FULL_VISIBILITY_MODE = 'full';
export const HYBRID_MAP_OPACITY = 0.18;

const allowedModes = [
    FOGGED_VISIBILITY_MODE,
    HYBRID_VISIBILITY_MODE,
    FULL_VISIBILITY_MODE
];

// This value is supplied by the server's /config response. There is no viewer
// preference or UI control: the server owner owns this policy.
export const normalizeWorldVisibilityMode = (value) => (
    allowedModes.includes(value) ? value : FOGGED_VISIBILITY_MODE
);
