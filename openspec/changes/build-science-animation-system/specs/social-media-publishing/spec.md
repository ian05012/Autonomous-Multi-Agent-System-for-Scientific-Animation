## ADDED Requirements

### Requirement: Generate YouTube-optimized title and description
The Social Media Agent SHALL generate a YouTube video title (≤100 characters) and description (≤5000 characters, including hashtags and timestamps) using an LLM, based on the storyboard content.

#### Scenario: YouTube metadata generated
- **WHEN** Social Media Agent receives the approved storyboard
- **THEN** it returns a `YouTubeMetadata` object with `title` (≤100 chars), `description` (≤5000 chars), and a list of ≥5 relevant `tags`

### Requirement: Upload video to YouTube
The system SHALL upload the final MP4 to YouTube using the YouTube Data API v3 with the generated metadata, returning the published video URL.

#### Scenario: Successful YouTube upload
- **WHEN** valid OAuth2 credentials are configured and final video exists
- **THEN** system uploads the MP4 as an unlisted video (default) and returns `youtube_url` in the format `https://youtu.be/<video_id>`

#### Scenario: YouTube upload failure
- **WHEN** upload fails (quota exceeded, auth error, network failure)
- **THEN** system retries up to 3 times with exponential backoff; if all retries fail, the error is logged and the user is notified with the local video path

### Requirement: Generate Instagram caption
The Social Media Agent SHALL generate an Instagram caption (≤2200 characters) with relevant hashtags (10–30 hashtags) for the video content.

#### Scenario: Instagram caption generated
- **WHEN** Social Media Agent receives the approved storyboard
- **THEN** it returns an `InstagramMetadata` object with `caption` (≤2200 chars including hashtags)

### Requirement: Upload video to Instagram via Graph API
The system SHALL upload the final MP4 as an Instagram Reel using the Instagram Graph API, returning the published post URL.

#### Scenario: Successful Instagram upload
- **WHEN** valid Instagram Graph API credentials are configured and final video exists
- **THEN** system uploads the video and returns `instagram_url` for the published reel

#### Scenario: Instagram upload failure
- **WHEN** upload fails
- **THEN** error is logged and user is notified; pipeline does not fail — social media upload is best-effort
