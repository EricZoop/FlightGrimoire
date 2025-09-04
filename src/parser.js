// --- Time Conversion Helper ---
function getStartOfGpsWeek() {
    const today = new Date();
    // GPS week starts on Sunday. weekday() is Monday=0, Sunday=6
    const daysSinceSunday = (today.getDay()) % 7; // Sunday is 0 in JS
    const startOfWeek = new Date(today);
    startOfWeek.setDate(today.getDate() - daysSinceSunday);
    startOfWeek.setHours(0, 0, 0, 0);
    return startOfWeek;
}

function itowToDatetimeStr(itowMs) {
    const startOfWeek = getStartOfGpsWeek();
    const timestamp = new Date(startOfWeek.getTime() + itowMs);

    const year = timestamp.getFullYear();
    const month = String(timestamp.getMonth() + 1).padStart(2, '0');
    const day = String(timestamp.getDate()).padStart(2, '0');
    const hours = String(timestamp.getHours()).padStart(2, '0');
    const minutes = String(timestamp.getMinutes()).padStart(2, '0');
    const seconds = String(timestamp.getSeconds()).padStart(2, '0');
    const milliseconds = String(timestamp.getMilliseconds()).padStart(3, '0');

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}.${milliseconds}`;
}

// --- UBX Parsing Functions ---
function parseUbxNavHpposllh(data) {
    if (data.length < 36) return null;

    try {
        const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
        const flags = view.getUint8(3);
        const iTOW = view.getUint32(4, true);
        const lon = view.getInt32(8, true);
        const lat = view.getInt32(12, true);
        const hMSL = view.getInt32(20, true);
        const lonHp = view.getInt8(24);
        const latHp = view.getInt8(25);
        const hMSLHp = view.getInt8(27);

        const lonHp_final = (lon * 1e-7) + (lonHp * 1e-9);
        const latHp_final = (lat * 1e-7) + (latHp * 1e-9);
        const hMSLHp_final = (hMSL * 1e-3) + (hMSLHp * 1e-4);

        const isValid = (flags & 0x01) === 0;
        if (!isValid) return null;

        return { iTOW, latitude: latHp_final, longitude: lonHp_final, height_msl: hMSLHp_final };
    } catch (error) {
        return null;
    }
}

function findUbxMessages(data) {
    const messages = [];
    let i = 0;
    while (i < data.length - 8) {
        if (data[i] === 0xB5 && data[i + 1] === 0x62) {
            try {
                if (i + 6 > data.length) { i++; continue; }
                const msgClass = data[i + 2];
                const msgId = data[i + 3];
                const length = data[i + 4] | (data[i + 5] << 8);
                if (i + 8 + length > data.length) { i++; continue; }

                const payload = data.slice(i + 6, i + 6 + length);
                const ckARcvd = data[i + 6 + length];
                const ckBRcvd = data[i + 7 + length];
                let calcCkA = 0, calcCkB = 0;
                for (let j = i + 2; j < i + 6 + length; j++) {
                    calcCkA = (calcCkA + data[j]) & 0xFF;
                    calcCkB = (calcCkB + calcCkA) & 0xFF;
                }

                if (ckARcvd === calcCkA && ckBRcvd === calcCkB) {
                    messages.push([msgClass, msgId, payload]);
                    i += 8 + length;
                } else { i++; }
            } catch (error) { i++; }
        } else { i++; }
    }
    return messages;
}

// --- CSV Generation ---
function generateCsvFromUbxData(binaryData) {
    const allMessages = findUbxMessages(binaryData);
    const navHpposllhPayloads = allMessages
        .filter(([msgClass, msgId]) => msgClass === 0x01 && msgId === 0x14)
        .map(([, , payload]) => payload);

    if (navHpposllhPayloads.length === 0) {
        throw new Error('No valid UBX-NAV-HPPOSLLH messages found.');
    }

    let csvContent = 'time,latitude,longitude,height_msl\n';
    let count = 0;
    for (const payload of navHpposllhPayloads) {
        const parsedData = parseUbxNavHpposllh(payload);
        if (parsedData) {
            const timeStr = itowToDatetimeStr(parsedData.iTOW);
            csvContent += `${timeStr},${parsedData.latitude.toFixed(9)},${parsedData.longitude.toFixed(9)},${parsedData.height_msl.toFixed(4)}\n`;
            count++;
        }
    }
    console.log(`Successfully processed ${count} records`);
    return csvContent;
}

function generateDownloadName() {
    const now = new Date();
    const year = now.getUTCFullYear();
    const month = String(now.getUTCMonth() + 1).padStart(2, '0');
    const day = String(now.getUTCDate()).padStart(2, '0');
    const hours = String(now.getUTCHours()).padStart(2, '0');
    const minutes = String(now.getUTCMinutes()).padStart(2, '0');
    const seconds = String(now.getUTCSeconds()).padStart(2, '0');
    return `RTK_Rover_${year}-${month}-${day}_${hours}-${minutes}-${seconds}`;
}

/**
 * Parses a UBX file and returns the CSV content and a generated filename.
 * @param {File} file The UBX file to process.
 * @returns {Promise<{success: boolean, filename?: string, csvContent?: string, error?: string}>}
 */
export async function parseUbxFile(file) {
    try {
        const arrayBuffer = await file.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);
        const csvContent = generateCsvFromUbxData(uint8Array);
        const csvFilename = `${generateDownloadName()}.csv`;
        return { success: true, filename: csvFilename, csvContent: csvContent };
    } catch (error) {
        console.error('Error processing file:', error);
        return { success: false, error: error.message };
    }
}