import CoreBluetooth
import Combine
import Foundation

/// CoreBluetooth transport for the Pybricks GATT service.
///
/// Commands use the Pybricks WRITE_STDIN command (0x06). The matching hub
/// program sends `rdy` before accepting a command, then `ack:<cmd>` after it
/// executes it. Commands are deliberately fixed at three ASCII bytes.
final class PybricksHubController: NSObject, ObservableObject {
    private let serviceUUID = CBUUID(string: "C5F50001-8280-46DA-89F4-6D8051E4AEEF")
    private let commandEventUUID = CBUUID(string: "C5F50002-8280-46DA-89F4-6D8051E4AEEF")

    @Published private(set) var discoveredHubs: [CBPeripheral] = []
    @Published private(set) var isConnected = false
    @Published private(set) var connectedName = ""
    @Published private(set) var statusText = "Starting Bluetooth…"
    @Published private(set) var message = "Power on the hub, then scan."
    @Published private(set) var canSend = false
    @Published private(set) var commandLog: [CommandLogEntry] = []

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var commandEventCharacteristic: CBCharacteristic?
    private var receivedStdout = Data()
    private var awaitingAck: String?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
    }

    func scan() {
        guard central.state == .poweredOn else {
            statusText = "Bluetooth is unavailable"
            return
        }
        discoveredHubs.removeAll()
        message = "Scanning for Pybricks hubs…"
        central.scanForPeripherals(withServices: [serviceUUID], options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
    }

    func connect(to peripheral: CBPeripheral) {
        central.stopScan()
        message = "Connecting to \(peripheral.name ?? "hub")…"
        self.peripheral = peripheral
        central.connect(peripheral)
    }

    func disconnect() {
        if let peripheral {
            central.cancelPeripheralConnection(peripheral)
        }
    }

    func send(command: String) {
        guard command.utf8.count == 3,
              canSend,
              let peripheral,
              let characteristic = commandEventCharacteristic else { return }

        canSend = false
        awaitingAck = command
        appendLog("→ \(command)")
        message = "Sending \(command)…"

        // 0x06 is Pybricks WRITE_STDIN; payload is read by stdin.buffer on hub.
        var packet = Data([0x06])
        packet.append(contentsOf: command.utf8)
        peripheral.writeValue(packet, for: characteristic, type: .withResponse)
    }

    private func processStdout(_ data: Data) {
        receivedStdout.append(data)

        // The demo hub program has an unframed, fixed-size protocol:
        // `rdy` (3 bytes) and `ack:` + command (7 bytes). BLE may combine
        // them in one notification or split them across notifications.
        while !receivedStdout.isEmpty {
            if receivedStdout.starts(with: Data("rdy".utf8)) {
                guard receivedStdout.count >= 3 else { return }
                receivedStdout.removeFirst(3)
                canSend = true
                message = "Ready"
            } else if receivedStdout.starts(with: Data("ack:".utf8)) {
                guard receivedStdout.count >= 7 else { return }
                // `removeFirst()` may leave Data with a non-zero start index.
                // Use collection offsets, not absolute integer indexes, or an
                // `ack:fwd` following `rdy` can be decoded as `ack:ck`.
                let commandData = Data(receivedStdout.dropFirst(4).prefix(3))
                receivedStdout.removeFirst(7)
                let command = String(decoding: commandData, as: UTF8.self)
                appendLog("← ack:\(command)", isAcknowledgement: true)
                message = "Acknowledged: \(command)"
                awaitingAck = nil
            } else {
                // Unexpected stdout. Drop one byte to recover synchronization.
                receivedStdout.removeFirst()
            }
        }
    }

    private func appendLog(_ text: String, isAcknowledgement: Bool = false) {
        commandLog.append(CommandLogEntry(text: text, isAcknowledgement: isAcknowledgement))
        // Keep the UI responsive during a long remote-control session.
        if commandLog.count > 100 {
            commandLog.removeFirst(commandLog.count - 100)
        }
    }
}

struct CommandLogEntry: Identifiable {
    let id = UUID()
    let text: String
    let isAcknowledgement: Bool
}

extension PybricksHubController: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn:
            statusText = "Ready to scan"
            scan()
        case .unauthorized:
            statusText = "Bluetooth permission denied"
            message = "Allow Bluetooth access in iOS Settings."
        default:
            statusText = "Bluetooth is unavailable"
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String: Any], rssi RSSI: NSNumber) {
        guard !discoveredHubs.contains(where: { $0.identifier == peripheral.identifier }) else { return }
        discoveredHubs.append(peripheral)
        message = "Select a hub to connect."
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.delegate = self
        connectedName = peripheral.name ?? "Pybricks hub"
        statusText = "Discovering services…"
        peripheral.discoverServices([serviceUUID])
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        message = "Connection failed: \(error?.localizedDescription ?? "unknown error")"
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        isConnected = false
        canSend = false
        commandEventCharacteristic = nil
        awaitingAck = nil
        receivedStdout.removeAll()
        statusText = "Disconnected"
        message = error.map { "Disconnected: \($0.localizedDescription)" } ?? "Disconnected"
    }
}

extension PybricksHubController: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil, let services = peripheral.services else {
            message = "Could not discover Pybricks service."
            return
        }
        for service in services where service.uuid == serviceUUID {
            peripheral.discoverCharacteristics([commandEventUUID], for: service)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard error == nil,
              let characteristic = service.characteristics?.first(where: { $0.uuid == commandEventUUID }) else {
            message = "Pybricks command characteristic was not found."
            return
        }
        commandEventCharacteristic = characteristic
        peripheral.setNotifyValue(true, for: characteristic)
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, characteristic.uuid == commandEventUUID, characteristic.isNotifying else {
            message = "Could not subscribe to hub messages."
            return
        }
        isConnected = true
        statusText = "Connected"
        message = "Start the Pybricks hub program; waiting for rdy."
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, characteristic.uuid == commandEventUUID, let value = characteristic.value, !value.isEmpty else { return }
        switch value[0] {
        case 0x01: // Pybricks WRITE_STDOUT event
            processStdout(Data(value.dropFirst()))
        case 0x00:
            message = "Hub status updated"
        default:
            message = "Hub event: 0x\(String(value[0], radix: 16))"
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error {
            canSend = true
            awaitingAck = nil
            message = "Write failed: \(error.localizedDescription)"
        }
    }
}
