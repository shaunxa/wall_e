import SwiftUI

@main
struct PybricksRemoteApp: App {
    @StateObject private var hub = PybricksHubController()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(hub)
        }
    }
}
