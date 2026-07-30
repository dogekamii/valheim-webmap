const actionListeners = {};

const addActionListener = (type, func) => {
    const listeners = actionListeners[type] || [];
    listeners.push(func);
    actionListeners[type] = listeners;
};

const getActionListeners = (type) => actionListeners[type] || [];

const actions = {
    players: (message) => {
        if (message.length > 64 || !message.startsWith('players\n')) return;
        try {
            const value = JSON.parse(message.slice(8));
            if (!value || Object.keys(value).length !== 1 || !Number.isInteger(value.online) || value.online < 0 || value.online > 10000) return;
            getActionListeners('players').forEach(func => func(value));
        } catch (_) { }
    },
    pin: (message) => {
        const lines = message.split('\n');
        if (lines.length !== 7 || lines.shift() !== 'pin') return;
        const xz = lines[4].split(',').map(Number);
        if (xz.length !== 2 || !xz.every(Number.isFinite) || xz.some(value => Math.abs(value) > 12000)) return;
        const pin = { id: lines[1], uid: lines[0], type: lines[2], name: lines[3], x: xz[0], z: xz[1], text: lines[5] };
        getActionListeners('pin').forEach(func => func(pin));
    },
    rmpin: (message) => {
        const lines = message.split('\n');
        if (lines.length !== 2 || lines[0] !== 'rmpin' || !lines[1]) return;
        getActionListeners('rmpin').forEach(func => func(lines[1]));
    }
};

Object.keys(actions).forEach(key => { actionListeners[key] = []; });

let socket;
let reconnectTimer;
let connectionTries = 0;
let reloading = false;

const clearReconnectTimer = () => {
    clearTimeout(reconnectTimer);
    reconnectTimer = undefined;
};

const closeSocket = () => {
    if (!socket) return;
    const previous = socket;
    socket = undefined;
    previous.onopen = null;
    previous.onmessage = null;
    previous.onclose = null;
    previous.onerror = null;
    previous.close();
};

const reload = () => {
    if (reloading) return;
    reloading = true;
    clearReconnectTimer();
    closeSocket();
    window.location.reload();
};

const scheduleReconnect = (closedSocket) => {
    if (reloading || socket !== closedSocket) return;
    socket = undefined;
    clearReconnectTimer();
    connectionTries = Math.min(connectionTries + 1, 7);
    const delay = Math.min(60000, 1000 * (2 ** Math.min(connectionTries, 6)));
    const jitter = Math.floor(Math.random() * 1001);
    reconnectTimer = setTimeout(init, delay + jitter);
};

const init = () => {
    if (reloading) return;
    clearReconnectTimer();
    closeSocket();
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const nextSocket = new WebSocket(`${protocol}//${location.host}/`);
    let playersRequested = false;
    socket = nextSocket;
    nextSocket.onmessage = (event) => {
        if (reloading || socket !== nextSocket || typeof event.data !== 'string' || event.data.length > 2048) return;
        if (event.data === 'reload') {
            reload();
            return;
        }
        if (event.data.startsWith('players\n')) actions.players(event.data);
        else if (event.data.startsWith('pin\n')) actions.pin(event.data);
        else if (event.data.startsWith('rmpin\n')) actions.rmpin(event.data);
    };
    nextSocket.onopen = () => {
        if (reloading || socket !== nextSocket || playersRequested) return;
        playersRequested = true;
        connectionTries = 0;
        nextSocket.send('players');
    };
    nextSocket.onclose = () => scheduleReconnect(nextSocket);
    nextSocket.onerror = () => { };
};

export default { init, addActionListener, getActionListeners };
