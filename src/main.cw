class Greeter {
    String message(String name) {
        String text = "Hello, "
        text.append(name)
        text.append("!\n")
        return(text)
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
