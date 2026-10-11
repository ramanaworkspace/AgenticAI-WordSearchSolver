Feature: Word Search Solver API contract

  Background:
    * url baseUrl

  Scenario: Health endpoint is available without authentication
    Given path 'health'
    When method get
    Then status 200
    And match response == { status: 'ok' }

  Scenario: Find words and report missing targets
    Given path 'api/v1/solve'
    And request
      """
      {
        "grid": [["C", "A", "T"], ["D", "O", "G"]],
        "words": ["CAT", "DOG", "MOUSE"]
      }
      """
    When method post
    Then status 200
    And match response ==
      """
      {
        "grid_size": {"rows": 2, "columns": 3},
        "results": [
          {
            "word": "CAT",
            "found": true,
            "start": {"row": 0, "column": 0},
            "end": {"row": 0, "column": 2},
            "direction": "east"
          },
          {
            "word": "DOG",
            "found": true,
            "start": {"row": 1, "column": 0},
            "end": {"row": 1, "column": 2},
            "direction": "east"
          }
        ],
        "not_found": ["MOUSE"]
      }
      """

  Scenario: Match words in forward and reverse diagonal directions
    Given path 'api/v1/solve'
    And request
      """
      {
        "grid": [["C", "X", "X"], ["X", "A", "X"], ["X", "X", "T"]],
        "words": ["CAT", "TAC"]
      }
      """
    When method post
    Then status 200
    And match response.results ==
      """
      [
        {
          "word": "CAT",
          "found": true,
          "start": {"row": 0, "column": 0},
          "end": {"row": 2, "column": 2},
          "direction": "southeast"
        },
        {
          "word": "TAC",
          "found": true,
          "start": {"row": 2, "column": 2},
          "end": {"row": 0, "column": 0},
          "direction": "northwest"
        }
      ]
      """
    And match response.not_found == []

  Scenario: Normalize and deduplicate target words
    Given path 'api/v1/solve'
    And request
      """
      {
        "grid": [[" c ", "a", "t"]],
        "words": [" cat ", "CAT", "Cat"]
      }
      """
    When method post
    Then status 200
    And match response.results ==
      """
      [
        {
          "word": "CAT",
          "found": true,
          "start": {"row": 0, "column": 0},
          "end": {"row": 0, "column": 2},
          "direction": "east"
        }
      ]
      """
    And match response.not_found == []

  Scenario: Return one deterministic result for a single-letter word
    Given path 'api/v1/solve'
    And request { grid: [['A', 'B', 'C']], words: ['B'] }
    When method post
    Then status 200
    And match response.results ==
      """
      [
        {
          "word": "B",
          "found": true,
          "start": {"row": 0, "column": 1},
          "end": {"row": 0, "column": 1},
          "direction": "north"
        }
      ]
      """

  Scenario: Return the first row-major occurrence only
    Given path 'api/v1/solve'
    And request { grid: [['C', 'A', 'T', 'C', 'A', 'T']], words: ['CAT'] }
    When method post
    Then status 200
    And match response.results ==
      """
      [
        {
          "word": "CAT",
          "found": true,
          "start": {"row": 0, "column": 0},
          "end": {"row": 0, "column": 2},
          "direction": "east"
        }
      ]
      """

  Scenario: Solve the full animal worksheet grid through the JSON endpoint
    Given path 'api/v1/solve'
    And request
      """
      {
        "grid": [
          ["J", "F", "R", "O", "G", "J", "Y", "I"],
          ["D", "G", "O", "A", "T", "Y", "W", "M"],
          ["M", "U", "X", "C", "B", "V", "O", "L"],
          ["L", "S", "C", "I", "E", "J", "L", "I"],
          ["B", "E", "A", "K", "A", "S", "F", "O"],
          ["Q", "A", "E", "D", "R", "W", "D", "N"],
          ["S", "L", "Y", "C", "R", "A", "B", "D"],
          ["F", "I", "S", "H", "Z", "N", "J", "H"]
        ],
        "words": ["BEAR", "CRAB", "DUCK", "FISH", "FROG", "GOAT", "LION", "SEAL", "SWAN", "WOLF"]
      }
      """
    When method post
    Then status 200
    And match response ==
      """
      {
        "grid_size": {"rows": 8, "columns": 8},
        "results": [
          {"word": "BEAR", "found": true, "start": {"row": 2, "column": 4}, "end": {"row": 5, "column": 4}, "direction": "south"},
          {"word": "CRAB", "found": true, "start": {"row": 6, "column": 3}, "end": {"row": 6, "column": 6}, "direction": "east"},
          {"word": "DUCK", "found": true, "start": {"row": 1, "column": 0}, "end": {"row": 4, "column": 3}, "direction": "southeast"},
          {"word": "FISH", "found": true, "start": {"row": 7, "column": 0}, "end": {"row": 7, "column": 3}, "direction": "east"},
          {"word": "FROG", "found": true, "start": {"row": 0, "column": 1}, "end": {"row": 0, "column": 4}, "direction": "east"},
          {"word": "GOAT", "found": true, "start": {"row": 1, "column": 1}, "end": {"row": 1, "column": 4}, "direction": "east"},
          {"word": "LION", "found": true, "start": {"row": 2, "column": 7}, "end": {"row": 5, "column": 7}, "direction": "south"},
          {"word": "SEAL", "found": true, "start": {"row": 3, "column": 1}, "end": {"row": 6, "column": 1}, "direction": "south"},
          {"word": "SWAN", "found": true, "start": {"row": 4, "column": 5}, "end": {"row": 7, "column": 5}, "direction": "south"},
          {"word": "WOLF", "found": true, "start": {"row": 1, "column": 6}, "end": {"row": 4, "column": 6}, "direction": "south"}
        ],
        "not_found": []
      }
      """

  Scenario: Reject a non-rectangular grid
    Given path 'api/v1/solve'
    And request { grid: [['A', 'B'], ['C']], words: ['ABC'] }
    When method post
    Then status 422

  Scenario: Reject a target word containing non-letters
    Given path 'api/v1/solve'
    And request { grid: [['C', 'A', 'T']], words: ['CAT1'] }
    When method post
    Then status 422

  Scenario Outline: Reject empty solver inputs
    Given path 'api/v1/solve'
    And request <payload>
    When method post
    Then status 422

    Examples:
      | payload                                      |
      | { grid: [], words: ['CAT'] }                 |
      | { grid: [['C', 'A', 'T']], words: [] }       |
      | { grid: [['C', 'A', 'T']], words: [''] }     |

  Scenario: Reject a grid cell containing more than one letter
    Given path 'api/v1/solve'
    And request { grid: [['CAT']], words: ['CAT'] }
    When method post
    Then status 422
