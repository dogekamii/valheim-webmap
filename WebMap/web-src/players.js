import ui from "./ui";
import websocket from "./websocket";

const init = () => {
    websocket.addActionListener('players', (aggregate) => {
        const online = Number.isInteger(aggregate.online) ? aggregate.online : 0;
        ui.onlineCount.textContent = String(Math.max(0, Math.min(10000, online)));
    });
};

export default { init };
