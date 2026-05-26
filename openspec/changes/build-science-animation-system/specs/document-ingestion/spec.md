## ADDED Requirements

### Requirement: Accept science article as plain text
The system SHALL accept a raw science article as plain UTF-8 text input and extract its title, abstract, and body sections into a normalized `DocumentContent` object.

#### Scenario: Valid plain-text article
- **WHEN** user provides a non-empty UTF-8 string with at least 200 words
- **THEN** system returns a `DocumentContent` with `source_type="text"`, populated `title` (or `"Untitled"` fallback), and `body` containing the full text

#### Scenario: Text too short
- **WHEN** user provides text with fewer than 50 words
- **THEN** system returns an error: `"Input text too short to generate a meaningful storyboard (minimum 50 words)"`

### Requirement: Accept PDF file input
The system SHALL accept a PDF file path, extract all readable text pages using `pdfplumber`, and return a normalized `DocumentContent` object.

#### Scenario: Valid PDF extraction
- **WHEN** user provides a valid PDF file path with extractable text
- **THEN** system extracts text from all pages, concatenates them, and returns `DocumentContent` with `source_type="pdf"`

#### Scenario: Scanned PDF with no extractable text
- **WHEN** PDF contains only scanned images (no selectable text)
- **THEN** system returns an error: `"PDF contains no extractable text. OCR is not supported in this version."`

### Requirement: Accept URL input
The system SHALL fetch the content of a given URL using `requests` + `BeautifulSoup`, strip navigation/ads, and return the main article text as `DocumentContent`.

#### Scenario: Valid article URL
- **WHEN** user provides a valid HTTPS URL that responds with HTML containing article content
- **THEN** system returns `DocumentContent` with `source_type="url"` and extracted body text

#### Scenario: URL fetch failure
- **WHEN** URL is unreachable (network error, 4xx/5xx response, timeout > 15s)
- **THEN** system returns an error: `"Failed to fetch URL: {reason}"`
