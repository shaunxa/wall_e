import SwiftUI

@main
struct WallECompanionApp: App {
    @StateObject private var robot = WallEHubController()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(robot)
        }
    }
}
