// Optional Structurizr DSL scaffold for c4-archi-model.
// Replace every placeholder element with evidence-backed model data.
// Do not deliver this scaffold unchanged as if it described the user's system.

workspace "Architecture Model" "Evidence-backed C4 architecture model" {
    !identifiers hierarchical

    model {
        user = person "User" "A placeholder person; replace with a real role from the sources."

        targetSystem = softwareSystem "Target Software System" "Replace with the system in scope." {
            application = container "Application" "Replace with an evidence-backed responsibility." "Technology unknown"
            dataStore = container "Data Store" "Replace with an evidence-backed storage responsibility." "Technology unknown"

            application -> dataStore "Reads from and writes to"
        }

        user -> targetSystem "Uses"
    }

    views {
        systemContext targetSystem "SystemContext" {
            include *
            autoLayout lr
        }

        container targetSystem "Containers" {
            include *
            autoLayout lr
        }

        styles {
            element "Person" {
                shape person
            }
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
        }
    }
}
