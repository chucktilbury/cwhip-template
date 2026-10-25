class Greeter {
    String message(String name) {
        return("Hello, " + name + "!\n")
    }
}

start {
    dict options = [
        "name": "world",
    ]
    Greeter greeter = Greeter()
    String<String> greeting = greeter.message
    print(greeting(options["name"]))
}
