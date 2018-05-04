class CoreRest {
    constructor() {
    }

    async sessions(callback) {
        const response = await $.getJSON('/sessions');
        callback(response);
    }
}
