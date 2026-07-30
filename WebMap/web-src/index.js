import constants from "./constants";
import websocket from "./websocket";
import map from "./map";
import players from "./players";
import ui from "./ui";
import { normalizeWorldVisibilityMode } from "./visibility";

const mapImage = document.createElement('img');
const fogImage = document.createElement('img');

const fetchMap = () => new Promise((resolve) => {
    fetch('map').then(response => response.blob()).then((blob) => {
        mapImage.onload = resolve;
        mapImage.src = URL.createObjectURL(blob);
    });
});

const fetchFog = () => new Promise((resolve) => {
    fogImage.onload = resolve;
    fogImage.src = 'fog';
});

const createStyleSheet = (styles = '') => {
    const style = document.createElement('style');
    style.appendChild(document.createTextNode(styles));
    document.head.appendChild(style);
};

const parseVector3 = (value) => {
    const parts = value.split(',');
    return { x: parseFloat(parts[0]), y: parseFloat(parts[1]), z: parseFloat(parts[2]) };
};

const fetchConfig = fetch('config').then(response => response.json()).then(config => {
    constants.CANVAS_WIDTH = config.texture_size || 2048;
    constants.CANVAS_HEIGHT = config.texture_size || 2048;
    constants.PIXEL_SIZE = config.pixel_size || 12;
    constants.EXPLORE_RADIUS = config.explore_radius || 100;
    constants.UPDATE_INTERVAL = config.update_interval || 1;
    constants.WORLD_NAME = config.world_name;
    constants.WORLD_START_POSITION = parseVector3(config.world_start_pos);
    constants.DEFAULT_ZOOM = config.default_zoom || 200;
    constants.ALWAYS_MAP = config.always_map;
    constants.ALWAYS_VISIBLE = config.always_visible;
    constants.WORLD_VISIBILITY_MODE = normalizeWorldVisibilityMode(config.world_visibility_mode);
    document.title = `Valheim WebMap - ${constants.WORLD_NAME}`;
    createStyleSheet(`.map.smooth { transition: top ${constants.UPDATE_INTERVAL}s linear, left ${constants.UPDATE_INTERVAL}s linear; }`);
});

const setup = async () => {
    await Promise.all([fetchMap(), fetchFog(), fetchConfig]);
    map.init({ mapImage, fogImage, zoom: constants.DEFAULT_ZOOM, visibilityMode: constants.WORLD_VISIBILITY_MODE });
    map.addIcon({ type: 'start', x: constants.WORLD_START_POSITION.x, z: constants.WORLD_START_POSITION.z, static: true });

    fetch('pins').then(response => response.text()).then(text => {
        text.split('\n').forEach(line => {
            const parts = line.split(',');
            if (parts.length >= 7) {
                map.addIcon({ id: parts[1], uid: parts[0], type: parts[2], name: parts[3], x: Number(parts[4]), z: Number(parts[5]), text: parts[6], static: true }, false);
            }
        });
        map.updateIcons();
    });

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
