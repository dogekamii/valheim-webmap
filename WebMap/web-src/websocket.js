const actionListeners = {};

const addActionListener = (type, func) => {
    const listeners = actionListeners[type] || [];
    listeners.push(func);
    actionListeners[type] = listeners;
};

const getActionListeners = (type) => actionListeners[type] || [];

const actions = {
    players: (lines, message) => {
        const value = JSON.parse(message.replace(/^players\n/, ''));
        if (!value || !Number.isInteger(value.online) || value.online < 0 || value.online > 10000) return;
        getActionListeners('players').forEach(func => func(value));
    },
    pin: (lines) => {
        if (lines.length !== 6) return;
        const xz = lines[4].split(',').map(Number);
        if (xz.length !== 2 || !xz.every(Number.isFinite)) return;
        const pin = { id: lines[1], uid: lines[0], type: lines[2], name: lines[3], x: xz[0], z: xz[1], text: lines[5] };
        getActionListeners('pin').forEach(func => func(pin));
    },
    rmpin: (lines) => getActionListeners('rmpin').forEach(func => func(lines[0])),
    reload: () => window.location.reload()
};

Object.keys(actions).forEach(key => { actionListeners[key] = []; });

let socket;
let reconnectTimer;
let connectionTries = 0;

const scheduleReconnect = () => {
    clearTimeout(reconnectTimer);
    connectionTries += 1;
    const delay = Math.min(120000, connectionTries * connectionTries * 1000);
    const jitter = Math.floor(Math.random() * 1000);
    reconnectTimer = setTimeout(init, delay + jitter);
};

const init = () => {
    clearTimeout(reconnectTimer);
    if (socket) {
        socket.onclose = null;
        socket.close();
    }
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${protocol}//${location.host}/`);
    socket.addEventListener('message', (event) => {
        if (typeof event.data !== 'string') return;
        const message = event.data.trim();
        const lines = message.split('\n');
        const action = lines.shift();
        if (actions[action]) actions[action](lines, message);
    });
    socket.addEventListener('open', () => {
        connectionTries = 0;
        socket.send('players');
    });
    socket.addEventListener('close', scheduleReconnect);
};

export default { init, addActionListener, getActionListeners };
