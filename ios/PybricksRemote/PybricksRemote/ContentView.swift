import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var hub: PybricksHubController
    @StateObject private var faceMotion = FaceMotionController()

    var body: some View {
        NavigationStack {
            Group {
                if hub.isConnected {
                    connectedRemote
                } else {
                    VStack(spacing: 24) {
                        status
                        nearbyHubs
                        Spacer()
                    }
                    .padding(.top)
                }
            }
            .background(Color(uiColor: .systemBackground).ignoresSafeArea())
            .navigationTitle("Pybricks Remote")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItemGroup(placement: .topBarTrailing) {
                    if hub.isConnected {
                        status
                    }
                    if hub.isConnected {
                        Button("Disconnect") { hub.disconnect() }
                    } else {
                        Button("Scan") { hub.scan() }
                    }
                }
            }
            .task { hub.scan() }
            .onChange(of: hub.isConnected) { connected in
                if !connected { faceMotion.stop() }
            }
        }
    }

    private var status: some View {
        Label(hub.statusText, systemImage: hub.isConnected ? "dot.radiowaves.left.and.right" : "antenna.radiowaves.left.and.right")
            .font(.subheadline)
            .foregroundStyle(hub.isConnected ? .green : .secondary)
    }

    /// Designed around the iPhone 13's 390 × 844 point portrait display.
    /// The log scales with the available safe-area height instead of forcing
    /// a fixed screen size, so it remains usable on nearby iPhone sizes.
    private var connectedRemote: some View {
        GeometryReader { proxy in
            let buttonWidth = min(70, max(54, (proxy.size.width - 104) / 3))
            let logHeight = min(320, max(240, proxy.size.height * 0.40))

            VStack(spacing: 0) {
                remote(buttonWidth: buttonWidth)
                    .padding(.top, 8)

                Spacer(minLength: 16)

                commandLog(height: logHeight)
                    .padding(.bottom, 12)
            }
        }
    }

    private var nearbyHubs: some View {
        List {
            ForEach(hub.discoveredHubs, id: \.identifier) { peripheral in
                Button {
                    hub.connect(to: peripheral)
                } label: {
                    HStack {
                        VStack(alignment: .leading) {
                            Text(peripheral.name ?? "Unnamed Pybricks hub")
                            Text(peripheral.identifier.uuidString)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                    }
                }
            }
        }
        .overlay {
            if hub.discoveredHubs.isEmpty {
                VStack(spacing: 10) {
                    Image(systemName: "dot.radiowaves.left.and.right")
                        .font(.largeTitle)
                        .foregroundStyle(.secondary)
                    Text("No hub found")
                        .font(.headline)
                    Text("Turn on the hub and run a Pybricks program.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding()
            }
        }
    }

    private func remote(buttonWidth: CGFloat) -> some View {
        VStack(spacing: 10) {
            Text("Connected to \(hub.connectedName)")
                .foregroundStyle(.secondary)

            Toggle(isOn: $faceMotion.isTracking) {
                Label("Face control", systemImage: "faceid")
                    .font(.subheadline)
            }
            .toggleStyle(.switch)
            .onChange(of: faceMotion.isTracking) { enabled in
                if enabled {
                    faceMotion.onCommand = { command in hub.send(command: command) }
                    faceMotion.start()
                } else {
                    faceMotion.stop()
                }
            }

            if faceMotion.isTracking {
                VStack(spacing: 4) {
                    CameraPreview(session: faceMotion.previewSession)
                        .frame(width: 210, height: 132)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .overlay {
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(.secondary.opacity(0.35), lineWidth: 1)
                        }

                    Text(faceMotion.status)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            HStack(spacing: 10) {
                remoteButton("Forward", icon: "arrow.up", width: buttonWidth) { hub.send(command: "fwd") }
                remoteButton("Stop", icon: "stop.fill", tint: .red, width: buttonWidth) { hub.send(command: "stp") }
                remoteButton("Reverse", icon: "arrow.down", width: buttonWidth) { hub.send(command: "rev") }
            }

        }
        .padding(.horizontal)
    }

    private func commandLog(height: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("COMMAND LOG")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 7) {
                    ForEach(hub.commandLog) { item in
                        Text(item.text)
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(item.isAcknowledgement ? .green : .primary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(12)
            }
            .frame(height: height)
            .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
        }
        .padding(.horizontal)
    }

    private func remoteButton(_ title: String, icon: String, tint: Color = .blue, width: CGFloat, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon).font(.title2)
                Text(title)
            }
            .frame(width: width, height: 56)
        }
        .buttonStyle(.borderedProminent)
        .tint(tint)
        .disabled(!hub.canSend)
    }
}
