import SwiftUI
import UIKit

struct ContentView: View {
    @EnvironmentObject private var robot: WallEHubController
    @StateObject private var face = FaceMotionController()
    @StateObject private var speech = SpeechController()
    @State private var cameraLensIsOnLeft = false
    private let wallEMusicURL = URL(string: "https://www.youtube.com/watch?v=OLMffDM7hSI&list=RDOLMffDM7hSI&start_radio=1")!

    var body: some View {
        NavigationStack {
            Group {
                if robot.connected { remote } else { scanner }
            }
            .navigationTitle("Wall-E Companion")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(robot.connected ? "Disconnect" : "Scan") {
                        robot.connected ? robot.disconnect() : robot.scan()
                    }
                }
            }
            .task { robot.scan() }
        }
    }

    private var scanner: some View {
        List(robot.nearby, id: \.identifier) { hub in
            Button(hub.name ?? "Pybricks Hub") { robot.connect(hub) }
        }
        .overlay {
            if robot.nearby.isEmpty {
                VStack(spacing: 10) {
                    Image(systemName: "dot.radiowaves.left.and.right").font(.largeTitle)
                    Text("No hub found").font(.headline)
                    Text(robot.status).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }

    private var remote: some View {
        GeometryReader { geo in
            let landscape = geo.size.width > geo.size.height
            Group {
                if landscape {
                    HStack(alignment: .top, spacing: 12) {
                        if !cameraLensIsOnLeft { faceControlPanel }
                        robotControlPanel
                        if cameraLensIsOnLeft { faceControlPanel }
                    }
                } else {
                    VStack(spacing: 12) { faceControlPanel; robotControlPanel }
                }
            }
            .padding(.horizontal)
            .padding(.bottom)
            .padding(.top, landscape ? 0 : 16)
        }
        .onAppear { bindIntents() }
        .onChange(of: robot.connected) { _ in
            if !robot.connected { face.setEnabled(false); speech.stop() }
        }
    }

    private var faceControlPanel: some View {
        VStack(spacing: 10) {
            if face.enabled { facePreview }
            Toggle("Face control", isOn: $face.enabled)
                .onChange(of: face.enabled) { enabled in face.setEnabled(enabled) }
            if face.enabled {
                DisclosureGroup("Face distance: \(Int(face.minimumFaceWidth * 100))–\(Int(face.maximumFaceWidth * 100))%") {
                    VStack(spacing: 4) {
                        Slider(
                            value: Binding(
                                get: { Double(face.minimumFaceWidth) },
                                set: { face.minimumFaceWidth = min(CGFloat($0), face.maximumFaceWidth - 0.05) }
                            ),
                            in: 0.10...0.50,
                            step: 0.05
                        )
                        Text("Too far below \(Int(face.minimumFaceWidth * 100))% → move closer")
                        Slider(
                            value: Binding(
                                get: { Double(face.maximumFaceWidth) },
                                set: { face.maximumFaceWidth = max(CGFloat($0), face.minimumFaceWidth + 0.05) }
                            ),
                            in: 0.15...0.60,
                            step: 0.05
                        )
                        Text("Too close above \(Int(face.maximumFaceWidth * 100))% → back away")
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .top)
    }

    private var robotControlPanel: some View {
        VStack(spacing: 10) {
            robotStatus
            Text(robot.telemetry).font(.caption).foregroundStyle(.secondary)
            Button { speech.toggle() } label: { Label(speech.listening ? "Listening…" : "Voice command", systemImage: speech.listening ? "mic.fill" : "mic") }
                .buttonStyle(.bordered)
            Text(speech.transcript).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            HStack(spacing: 10) {
                command("Left", "arrow.turn.up.left") { robot.turnLeft() }
                command("Stop", "stop.fill", .red) { robot.stop() }
                command("Right", "arrow.turn.up.right") { robot.turnRight() }
            }
            HStack(spacing: 10) {
                command("Head L", "arrow.turn.up.left") { robot.head(-45) }
                command("Head R", "arrow.turn.up.right") { robot.head(45) }
            }
            Link(destination: wallEMusicURL) {
                Label("Play WALL-E music", systemImage: "music.note")
                    .frame(maxWidth: .infinity, minHeight: 38)
            }
            .buttonStyle(.borderedProminent)
            .tint(.purple)
            .disabled(robot.wheelsEnabled)
            Text(robot.wheelsEnabled
                 ? "Disable the wheels at Wall-E's shoulder before playing music."
                 : "Wall-E is stationary — opens YouTube Music.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .top)
    }

    private var robotStatus: some View {
        Label(robot.ready ? "Robot ready" : robot.status, systemImage: robot.ready ? "checkmark.circle.fill" : "hourglass")
            .foregroundStyle(robot.ready ? .green : .secondary)
    }

    private var facePreview: some View {
        VStack(spacing: 10) {
            CameraPreview(session: face.session, onInterfaceOrientationChange: updateCameraOrientation)
                .frame(width: 180, height: 112)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            if !robot.wheelsEnabled {
                Label("Wheels disabled — stopped", systemImage: "stop.circle.fill")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.red)
            }
            Text(face.status).font(.caption).foregroundStyle(.secondary)
        }
        .frame(width: 180, alignment: .top)
    }

    private func command(_ title: String, _ icon: String, _ tint: Color = .blue, action: @escaping () -> Void) -> some View {
        Button(action: action) { Label(title, systemImage: icon).frame(width: 72, height: 38) }.buttonStyle(.borderedProminent).tint(tint).disabled(!robot.connected)
    }

    private func updateCameraOrientation(_ interfaceOrientation: UIInterfaceOrientation) {
        // In this app's landscape layout, a left-facing interface orientation
        // puts the front camera lens on the left edge of the device.
        // Keep the preview on the opposite side of that lens.
        cameraLensIsOnLeft = interfaceOrientation == .landscapeLeft
        face.setInterfaceOrientation(interfaceOrientation)
    }

    private func bindIntents() {
        let act: (String) -> Void = { intent in
            switch intent {
            case "DRIVE_LEFT": robot.turnLeft()
            case "DRIVE_RIGHT": robot.turnRight()
            // With the assembled wheel orientation, positive logical drive
            // values move the chassis backward.
            case "REV": robot.drive(35, 35)
            case "FWD": robot.drive(-35, -35)
            case "HEAD_LEFT": robot.head(-45)
            case "HEAD_RIGHT": robot.head(45)
            default: robot.stop()
            }
        }
        face.onIntent = act; speech.onIntent = act
    }
}
