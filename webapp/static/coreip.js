const AF_INET = 2;
const AF_INET6 = 23;

function ord (string) {
    var str = string + '';
    var code = str.charCodeAt(0);

    if (code >= 0xD800 && code <= 0xDBFF) {
        // High surrogate (could change last hex to 0xDB7F to treat
        // high private surrogates as single characters)
        var hi = code;
        if (str.length === 1) {
            // This is just a high surrogate with no following low surrogate,
            // so we return its value;
            return code;
            // we could also throw an error as it is not a complete character,
            // but someone may want to know
        }
        var low = str.charCodeAt(1);
        return ((hi - 0xD800) * 0x400) + (low - 0xDC00) + 0x10000
    }
    if (code >= 0xDC00 && code <= 0xDFFF) {
        // Low surrogate
        // This is just a low surrogate with no preceding high surrogate,
        // so we return its value;
        return code;
        // we could also throw an error as it is not a complete character,
        // but someone may want to know
    }

    return code
}

function inetNtop (a) {
    var i = 0;
    var m = '';
    var c = [];

    a += '';
    if (a.length === 4) {
        // IPv4
        return [
            a.charCodeAt(0),
            a.charCodeAt(1),
            a.charCodeAt(2),
            a.charCodeAt(3)
        ].join('.');
    } else if (a.length === 16) {
        // IPv6
        for (i = 0; i < 16; i++) {
            c.push(((a.charCodeAt(i++) << 8) + a.charCodeAt(i)).toString(16));
        }
        return c.join(':')
            .replace(/((^|:)0(?=:|$))+:?/g, function (t) {
                m = (t.length > m.length) ? t : m;
                return t;
            })
            .replace(m || ' ', '::');
    } else {
        // Invalid length
        return false;
    }
}

function inetPton(a) {
    var r;
    var m;
    var x;
    var i;
    var j;
    var f = String.fromCharCode;

    // IPv4
    m = a.match(/^(?:\d{1,3}(?:\.|$)){4}/);
    if (m) {
        m = m[0].split('.');
        m = f(m[0]) + f(m[1]) + f(m[2]) + f(m[3]);
        // Return if 4 bytes, otherwise false.
        return m.length === 4 ? m : false;
    }
    r = /^((?:[\da-f]{1,4}(?::|)){0,8})(::)?((?:[\da-f]{1,4}(?::|)){0,8})$/;

    // IPv6
    m = a.match(r);
    if (m) {
        // Translate each hexadecimal value.
        for (j = 1; j < 4; j++) {
            // Indice 2 is :: and if no length, continue.
            if (j === 2 || m[j].length === 0) {
                continue;
            }
            m[j] = m[j].split(':');
            for (i = 0; i < m[j].length; i++) {
                m[j][i] = parseInt(m[j][i], 16);
                // Would be NaN if it was blank, return false.
                if (isNaN(m[j][i])) {
                    // Invalid IP.
                    return false;
                }
                m[j][i] = f(m[j][i] >> 8) + f(m[j][i] & 0xFF);
            }
            m[j] = m[j].join('');
        }
        x = m[1].length + m[3].length;
        if (x === 16) {
            return m[1] + m[3];
        } else if (x < 16 && m[2].length > 0) {
            return m[1] + (new Array(16 - x + 1))
                    .join('\x00') + m[3];
        }
    }

    // Invalid IP
    return false
}


class IpAddress {
    constructor(addressFamily, address) {
        console.log('ip address: ', addressFamily, address);
        this.addressFamily = addressFamily;
        this.address = address;
    }

    str() {
        return inetNtop(this.address);
    }
}

class IpPrefix {
    constructor(addressFamily, prefix) {
        this.addressFamily = addressFamily;
        if (this.addressFamily === AF_INET) {
            this.addressLength = 32;
        } else if (this.addressFamily == AF_INET6) {
            this.addressLength = 128;
        } else {
            throw Error(`invalid address family: ${addressFamily}`);
        }

        const values = prefix.split('/');
        console.log(`split prefix: ${values}`);
        if (values.length > 2) {
            throw Error(`invalid prefix: ${prefix}`);
        }

        if (values.length === 2) {
            this.prefixLength = parseInt(values[1]);
        } else {
            this.prefixLength = this.addressLength;
        }

        this.prefix = inetPton(values[0]);

        if (this.addressLength > this.prefixLength) {
            const addressBits = this.addressLength - this.prefixLength;
            let netMask = ((1 << this.prefixLength) - 1) << addressBits;
            prefix = '';
            //in xrange(-1, -(addrbits >> 3) - 2, -1)
            const stopValue = -(addressBits) - 2;
            for (let i = -1; i > stopValue; --i) {
                prefix = String.fromCharCode(ord(this.prefix[i]) & (netMask & 0xff)) + prefix;
                netMask >>= 8;
            }
            this.prefix = this.prefix.slice(0, stopValue) + prefix;
        }
    }

    getAddress(id) {
        if (id in [-1, 0, 1] && this.addressLength === this.prefixLength) {
            return new IpAddress(this.addressFamily, this.prefix);
        }

        const value = (1 << (this.addressLength - this.prefixLength)) - 1;
        console.log(`address length(${this.addressLength}) prefix length(${this.prefixLength}) value(${value})`);
        if (id === 0 || id > value || (this.addressFamily === AF_INET && id === value)) {
            throw Error(`invalid id for prefix ${this.prefix}: ${id}`);
        }

        let address = '';
        let prefixEndpoint = -1;
        console.log('stop condition: ', -(this.addressLength >> 3) - 1);
        for (let i = -1; i >  -(this.addressLength >> 3) - 1; --i) {
            console.log('i: ', i);
            prefixEndpoint = i;
            address = String.fromCharCode(ord(this.prefix[i]) | (id & 0xff)) + address;
            console.log('address: ', address);
            id >>= 8;
            console.log('id: ', id);
            if (!id) {
                break
            }
        }
        address = this.prefix.slice(0, prefixEndpoint) + address;
        return new IpAddress(this.addressFamily, address);
    }
}


