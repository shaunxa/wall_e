import CoreBluetooth
import Foundation

private let spikeService = CBUUID(string: "0000FD02-0000-1000-8000-00805F9B34FB")

private final class Scanner: NSObject, CBCentralManagerDelegate {
    private var central: CBCentralManager!
    private var hubs: [[String: Any]] = []

    func start() {
        central = CBCentralManager(delegate: self, queue: nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 10) { [weak self] in
            self?.finish()
        }
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        guard central.state == .poweredOn else {
            print("{\"error\":\"Bluetooth is not ready (state \\(central.state.rawValue))\"}")
            exit(1)
        }
        central.scanForPeripherals(withServices: [spikeService], options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String: Any], rssi RSSI: NSNumber) {
        hubs.append([
            "name": peripheral.name ?? advertisementData[CBAdvertisementDataLocalNameKey] ?? "Unnamed SPIKE hub",
            "address": peripheral.identifier.uuidString,
            "rssi": RSSI.intValue,
        ])
    }

    private func finish() {
        central.stopScan()
        let result: [String: Any] = ["hubs": hubs]
        let data = try! JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
        print(String(decoding: data, as: UTF8.self))
        exit(0)
    }
}

private let scanner = Scanner()
scanner.start()
RunLoop.main.run()
