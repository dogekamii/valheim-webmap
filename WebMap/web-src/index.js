import constants from "./constants";
import websocket from "./websocket";
import map from "./map";
import players from "./players";
import ui from "./ui";
import { normalizeWorldVisibilityMode } from "./visibility";

const MAX_PIN_RESPONSE_LENGTH = 1024 * 1024;
const MAX_PIN_ROWS = 5000;
const mapImage = document.createElement('img');
const fogImage = document.createElement('img');

const boundedNumber = (value, fallback, minimum, maximum) => (
    Number.isFinite(value) ? Math.min(maximum, Math.max(minimum, value)) : fallback
);

const loadImage = (image, source) => new Promise((resolve, reject) => {
    image.onload = resolve;
    image.onerror = reject;
    image.src = source;
});

const createStyleSheet = (styles = '') => {
    const style = document.createElement('style');
    style.appendChild(document.createTextNode(styles));
    document.head.appendChild(style);
};

const fetchConfig = async () => {
    const response = await fetch('config', { cache: 'no-store' });
    if (!response.ok) throw new Error('configuration unavailable');
    const config = await response.json();
    if (!config || typeof config.map_digest !== 'string' || !/^[0-9a-f]{64}$/.test(config.map_digest)) {
        throw new Error('map unavailable');
    }
    constants.CANVAS_WIDTH = Math.round(boundedNumber(config.texture_size, 2048, 256, 2048));
    constants.CANVAS_HEIGHT = constants.CANVAS_WIDTH;
    constants.COORD_OFFSET = constants.CANVAS_WIDTH / 2;
    constants.PIXEL_SIZE = boundedNumber(config.pixel_size, 12, 2, 100);
    constants.EXPLORE_RADIUS = boundedNumber(config.explore_radius, 100, 0, 500);
    constants.UPDATE_INTERVAL = boundedNumber(config.update_interval, 1, 0.25, 60);
    constants.DEFAULT_ZOOM = Math.round(boundedNumber(config.default_zoom, 100, 50, 800));
    constants.ALWAYS_MAP = config.always_map === true;
    constants.ALWAYS_VISIBLE = config.always_visible === true;
    constants.WORLD_VISIBILITY_MODE = normalizeWorldVisibilityMode(config.world_visibility_mode);
    const startX = boundedNumber(config.world_start_x, 0, -12000, 12000);
    const startZ = boundedNumber(config.world_start_z, 0, -12000, 12000);
    document.title = 'Valheim WebMap';
    createStyleSheet(`.map.smooth { transition: top ${constants.UPDATE_INTERVAL}s linear, left ${constants.UPDATE_INTERVAL}s linear; }`);
    return { mapDigest: config.map_digest, startX, startZ };
};

const loadPins = async () => {
    const response = await fetch('pins', { cache: 'no-store' });
    if (!response.ok) return;
    const text = await response.text();
    if (text.length > MAX_PIN_RESPONSE_LENGTH) return;
    text.split('\n', MAX_PIN_ROWS).forEach(line => {
        if (!line || line.length > 512) return;
        const parts = line.split(',');
        if (parts.length !== 7) return;
        const x = Number(parts[4]);
        const z = Number(parts[5]);
        if (!Number.isFinite(x) || !Number.isFinite(z) || Math.abs(x) > 12000 || Math.abs(z) > 12000) return;
        map.addIcon({ id: parts[1], uid: parts[0], type: parts[2], name: parts[3], x, z, text: parts[6], static: true }, false);
    });
    map.updateIcons();
};

const setup = async () => {
    const config = await fetchConfig();
    await Promise.all([
        loadImage(mapImage, `map?v=${encodeURIComponent(config.mapDigest)}`),
        loadImage(fogImage, 'fog')
    ]);
    map.init({ mapImage, fogImage, zoom: constants.DEFAULT_ZOOM, visibilityMode: constants.WORLD_VISIBILITY_MODE });
    map.addIcon({ type: 'start', x: config.startX, z: config.startZ, static: true });
    await loadPins();

    websocket.addActionListener('pin', pin => map.addIcon(pin));
    websocket.addActionListener('rmpin', pinId => map.removeIconById(pinId));
    window.addEventListener('resize', () => map.update());
    ui.menuBtn.addEventListener('click', () => ui.menu.classList.toggle('menuOpen'));

    const hideCheckboxes = ui.menu.querySelectorAll('.hideIconTypeCheckbox');
    hideCheckboxes.forEach(element => element.addEventListener('change', () => {
        map.setIconTypeHidden(element.dataset.hide, element.checked || ui.hideAll.checked);
        if (element.dataset.hide === 'all') {
            hideCheckboxes.forEach(other => map.setIconTypeHidden(other.dataset.hide, element.checked || other.checked));
        }
        map.updateIcons();
    }));

    players.init();
    websocket.init();
};

setup();
