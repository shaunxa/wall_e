import Combine
import CoreBluetooth
import Foundation

final class WallEHubController: NSObject, ObservableObject {
    private let serviceUUID = CBUUID(string: "C5F50001-8280-46DA-89F4-6D8051E4AEEF")
    private let commandUUID = CBUUID(string: "C5F50002-8280-46DA-89F4-6D8051E4AEEF")

    @Published private(set) var nearby: [CBPeripheral] = []
    @Published private(set) var connected = false
    @Published private(set) var ready = false
    @Published private(set) var status = "Starting Bluetooth…"
    @Published private(set) var telemetry = "Distance — · Reflection — · Touch —"
    @Published private(set) var log: [LogEntry] = []

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var commandCharacteristic: CBCharacteristic?
    private var stdout = Data()
    private var pendingCommands: [String] = []

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
    }

    func scan() {
        guard central.state == .poweredOn else { return }
        nearby.removeAll()
        status = "Scanning for Pybricks hub…"
        central.scanForPeripherals(withServices: [serviceUUID], options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
    }

    func connect(_ peripheral: CBPeripheral) {
        central.stopScan()
        status = "Connecting…"
        self.peripheral = peripheral
        central.connect(peripheral)
    }

    func disconnect() {
        if let peripheral { central.cancelPeripheralConnection(peripheral) }
    }

    func drive(_ left: Int, _ right: Int) { send("DRV \(left) \(right)") }
    // Port F is mechanically mirrored. These signs were verified against the
    // assembled chassis: this pair pivots left/right in the expected direction.
    func turnLeft() { drive(35, -35) }
    func turnRight() { drive(-35, 35) }
    func stop() { send("STOP") }
    func head(_ angle: Int) { send("HEAD \(angle)") }

    func send(_ command: String) {
        // Let the manual controls be used as soon as BLE has subscribed. This
        // also makes STOP available while the hub program is starting.
        guard connected, let peripheral, let characteristic = commandCharacteristic else { return }
        pendingCommands.append(command)
        append("→ \(command)", kind: .outgoing)
        // Pybricks multiplexes its command/event characteristic.  0x06 means
        // "send these following bytes to the running program's stdin".
        var packet = Data([0x06])
        packet.append(Data((command + "\n").utf8))
        peripheral.writeValue(packet, for: characteristic, type: .withResponse)
    }

    private func append(_ text: String, kind: LogEntry.Kind = .info) {
        log.append(LogEntry(text: text, kind: kind))
        if log.count > 80 { log.removeFirst(log.count - 80) }
    }

    private func handleStdout(_ data: Data) {
        stdout.append(data)
        while let newline = stdout.firstIndex(of: 0x0A) {
            let line = String(decoding: stdout[..<newline], as: UTF8.self)
            stdout.removeSubrange(...newline)
            handleLine(line)
        }
    }

    private func handleLine(_ line: String) {
        let line = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !line.isEmpty else { return }
        if line == "READY" {
            ready = true
            status = "Connected — robot ready"
            append("← READY", kind: .ack)
        } else if line.hasPrefix("ACK") {
            if !pendingCommands.isEmpty { pendingCommands.removeFirst() }
            append("← \(line)", kind: .ack)
        } else if line.hasPrefix("SAFE") {
            append("← \(line)", kind: .warning)
            status = "Safety stop: \(line.dropFirst(5))"
        } else if line.hasPrefix("TEL ") {
            telemetry = String(line.dropFirst(4)).replacingOccurrences(of: " ", with: " · ")
        } else {
            append("← \(line)", kind: .info)
        }
    }
}

extension WallEHubController: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn { scan() }
        else { status = "Bluetooth is unavailable" }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String: Any], rssi RSSI: NSNumber) {
        guard !nearby.contains(where: { $0.identifier == peripheral.identifier }) else { return }
        nearby.append(peripheral)
        status = "Select your robot"
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.delegate = self
        peripheral.discoverServices([serviceUUID])
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        connected = false; ready = false; commandCharacteristic = nil
        status = "Disconnected"
    }
}

extension WallEHubController: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil, let service = peripheral.services?.first(where: { $0.uuid == serviceUUID }) else { status = "Pybricks service not found"; return }
        peripheral.discoverCharacteristics([commandUUID], for: service)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard error == nil, let characteristic = service.characteristics?.first(where: { $0.uuid == commandUUID }) else { status = "Command channel not found"; return }
        commandCharacteristic = characteristic
        peripheral.setNotifyValue(true, for: characteristic)
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, characteristic.isNotifying else { status = "Could not subscribe to robot"; return }
        connected = true
        if !ready { status = "Start the Pybricks program…" }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, let data = characteristic.value, !data.isEmpty else { return }
        if data[0] == 0x01 { handleStdout(Data(data.dropFirst())) }
    }
}

struct LogEntry: Identifiable {
    enum Kind { case outgoing, ack, warning, info }
    let id = UUID()
    let text: String
    let kind: Kind
}
