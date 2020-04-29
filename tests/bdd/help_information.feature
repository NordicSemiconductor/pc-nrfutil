Feature: Help information
  Scenario: User types pkg generate --help
    Given user types 'nrfutil pkg generate --help'
    When user press enter
    Then output contains 'Generate a zip package for distribution to apps that support Nordic DFU' and exit code is 0

  Scenario: User does not type mandatory arguments
    Given user types 'nrfutil pkg generate'
    When user press enter
    Then output contains 'Error: Missing argument 'ZIPFILE'.' and exit code is 2

    Scenario: User types --help
      Given user types 'nrfutil --help'
      When user press enter
      Then output contains 'Show this message and exit.' and exit code is 0
