execute_process(COMMAND "${HELLO_EXECUTABLE}"
    RESULT_VARIABLE status
    OUTPUT_VARIABLE output
    ERROR_VARIABLE error
    TIMEOUT 10)
if(NOT "${status}" STREQUAL "0"
        OR NOT "${output}" STREQUAL "Hello, world!\n"
        OR NOT "${error}" STREQUAL "")
    message(FATAL_ERROR
        "Unexpected greeting: status=${status}, stdout=[${output}], stderr=[${error}]")
endif()
