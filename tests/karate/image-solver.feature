Feature: Word Search image solver API contract

  Background:
    * url baseUrl
    * configure readTimeout = 90000

  Scenario: Recognize and solve the bundled animal worksheet
    Given path 'api/v1/solve/image'
    And multipart file image = { read: 'classpath:Animal Image.jpeg', filename: 'Animal Image.jpeg', contentType: 'image/jpeg' }
    And multipart field words = '["BEAR","CRAB","DUCK","FISH","FROG","GOAT","LION","SEAL","SWAN","WOLF"]'
    When method post
    Then status 200
    And match response.grid ==
      """
      [
        ["J", "F", "R", "O", "G", "J", "Y", "I"],
        ["D", "G", "O", "A", "T", "Y", "W", "M"],
        ["M", "U", "X", "C", "B", "V", "O", "L"],
        ["L", "S", "C", "I", "E", "J", "L", "I"],
        ["B", "E", "A", "K", "A", "S", "F", "O"],
        ["Q", "A", "E", "D", "R", "W", "D", "N"],
        ["S", "L", "Y", "C", "R", "A", "B", "D"],
        ["F", "I", "S", "H", "Z", "N", "J", "H"]
      ]
      """
    And match response.confidence == '#? _ >= 0.7 && _ <= 1'
    And match response.solution.grid_size == { rows: 8, columns: 8 }
      And match response.solution.results ==
        """
        [
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
        ]
        """
      And match response.solution.not_found == []

  Scenario: Solve only selected words while returning the full extracted grid
    Given path 'api/v1/solve/image'
    And multipart file image = { read: 'classpath:Animal Image.jpeg', filename: 'Animal Image.jpeg', contentType: 'image/jpeg' }
    And multipart field words = '["BEAR","FROG"]'
    When method post
    Then status 200
    And match response.grid == '#[8]'
    And match response.solution.results ==
      """
      [
        {"word": "BEAR", "found": true, "start": {"row": 2, "column": 4}, "end": {"row": 5, "column": 4}, "direction": "south"},
        {"word": "FROG", "found": true, "start": {"row": 0, "column": 1}, "end": {"row": 0, "column": 4}, "direction": "east"}
      ]
      """
    And match response.solution.not_found == []

  Scenario: Report a target word absent from the worksheet
    Given path 'api/v1/solve/image'
    And multipart file image = { read: 'classpath:Animal Image.jpeg', filename: 'Animal Image.jpeg', contentType: 'image/jpeg' }
    And multipart field words = '["BEAR","ZEBRA"]'
    When method post
    Then status 200
    And match response.solution.results[*].word == ['BEAR']
    And match response.solution.not_found == ['ZEBRA']

  Scenario: Normalize and deduplicate image endpoint target words
    Given path 'api/v1/solve/image'
    And multipart file image = { read: 'classpath:Animal Image.jpeg', filename: 'Animal Image.jpeg', contentType: 'image/jpeg' }
    And multipart field words = '["bear","BEAR"," frog "]'
    When method post
    Then status 200
    And match response.solution.results[*].word == ['BEAR', 'FROG']

  Scenario: Reject words that are not a JSON array
    Given path 'api/v1/solve/image'
    And multipart file image = { read: 'classpath:Animal Image.jpeg', filename: 'Animal Image.jpeg', contentType: 'image/jpeg' }
    And multipart field words = 'BEAR,FROG'
    When method post
    Then status 422

  Scenario: Reject an empty word list
    Given path 'api/v1/solve/image'
    And multipart file image = { read: 'classpath:Animal Image.jpeg', filename: 'Animal Image.jpeg', contentType: 'image/jpeg' }
    And multipart field words = '[]'
    When method post
    Then status 422

  Scenario: Reject an invalid uploaded media type
    Given path 'api/v1/solve/image'
    And multipart field image = { value: 'not an image', filename: 'puzzle.txt', contentType: 'text/plain' }
    And multipart field words = '["BEAR"]'
    When method post
    Then status 415
