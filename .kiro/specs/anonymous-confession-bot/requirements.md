# Requirements Document

## Introduction

This document specifies the requirements for an Anonymous Confession Bot system built on Telegram. The system allows users to submit confessions anonymously or with attribution, enables admin moderation, publishes approved content to a channel, and supports a community-driven comments and reactions system.

## Glossary

- **User**: A Telegram user who has registered with the bot
- **Confession**: A text submission from a user that may be posted anonymously or with attribution
- **Admin**: A user with elevated privileges to moderate confessions
- **Channel**: A Telegram channel where approved confessions are published
- **Comment**: User-provided advice or response to a published confession
- **Impact Points**: A score calculated based on user engagement (confessions, comments, reactions)
- **Anonymity Mode**: A user setting that determines default attribution for confessions
- **Pending State**: The status of a confession awaiting admin review
- **Community Acceptance Score**: A metric derived from likes, dislikes, and reports on user content
- **Row Level Security (RLS)**: A PostgreSQL security feature that restricts which rows users can access in database tables
- **Service Role**: The authenticated database role used by the Django application to access the database
- **Anonymous User**: An unauthenticated database role that should be denied direct access to application tables

## Requirements

### Requirement 1: User Registration and Profile Management

**User Story:** As a user, I want to register with the bot and manage my anonymity settings, so that I can control how my identity is presented when I submit confessions.

#### Acceptance Criteria

1. WHEN a user sends the /register command, THE System SHALL create a user profile with a unique identifier and default settings
2. WHEN a user sends the /anonymous_on command, THE System SHALL enable anonymous mode for that user's future confessions
3. WHEN a user sends the /anonymous_off command, THE System SHALL disable anonymous mode for that user's future confessions
4. WHEN a user sends the /profile command, THE System SHALL display the user's statistics including total confessions, total comments, and impact points
5. WHEN a user profile is created, THE System SHALL initialize all counters to zero

### Requirement 2: Confession Submission

**User Story:** As a user, I want to submit confessions with control over my attribution, so that I can share my thoughts while maintaining my desired level of privacy.

#### Acceptance Criteria

1. WHEN a user sends the /confess command, THE System SHALL prompt the user to enter their confession text
2. WHEN a user submits confession text, THE System SHALL create a confession record in pending state
3. WHEN a confession is created, THE System SHALL apply the user's current anonymity setting as the default attribution
4. WHEN a confession is submitted, THE System SHALL notify all admins of the new pending confession
5. WHEN a confession text exceeds 4096 characters, THE System SHALL reject the submission and inform the user of the character limit

### Requirement 3: Admin Moderation Workflow

**User Story:** As an admin, I want to review and moderate pending confessions, so that I can ensure appropriate content is published to the channel.

#### Acceptance Criteria

1. WHEN a new confession enters pending state, THE System SHALL send a notification to all configured admins with confession details and inline action buttons
2. WHEN an admin clicks the approve button, THE System SHALL change the confession state to approved and publish it to the configured channel
3. WHEN an admin clicks the reject button, THE System SHALL change the confession state to rejected and notify the submitting user
4. WHEN an admin sends the /pending command, THE System SHALL display all confessions in pending state with their IDs and preview text
5. WHEN an admin sends the /stats command, THE System SHALL display counts of pending confessions, approved confessions, rejected confessions, and total registered users
6. WHEN an admin sends the /delete command with a confession ID, THE System SHALL remove the confession from the database and delete it from the channel if published

### Requirement 4: Channel Publishing

**User Story:** As a system administrator, I want approved confessions to be automatically published to a designated channel, so that the community can view and engage with the content.

#### Acceptance Criteria

1. WHEN a confession is approved, THE System SHALL post the confession text to the configured Telegram channel
2. WHEN a confession is posted to the channel, THE System SHALL include an inline button labeled "View / Add Comments"
3. WHEN a confession is posted to the channel, THE System SHALL display the confession ID in the post
4. WHEN a confession is posted anonymously, THE System SHALL display "Anonymous" as the author
5. WHEN a confession is posted with attribution, THE System SHALL display the user's first name and username as the author

### Requirement 5: Comments and Advice System

**User Story:** As a user, I want to add comments to published confessions and interact with other users' comments, so that I can provide support and engage with the community.

#### Acceptance Criteria

1. WHEN a user clicks the "View / Add Comments" button on a channel post, THE System SHALL display existing comments and provide an option to add a new comment
2. WHEN a user sends the /comment command with a confession ID, THE System SHALL prompt the user to enter their comment text
3. WHEN a user submits a comment, THE System SHALL store the comment with a reference to the confession and the commenter's user ID
4. WHEN a user sends the /comments command with a confession ID, THE System SHALL display all comments for that confession in paginated format
5. WHEN a user views comments, THE System SHALL provide inline buttons for like, dislike, and report actions on each comment
6. WHEN a user clicks a like button on a comment, THE System SHALL increment the like count for that comment
7. WHEN a user clicks a dislike button on a comment, THE System SHALL increment the dislike count for that comment
8. WHEN a user clicks a report button on a comment, THE System SHALL increment the report count and notify admins if the report count exceeds a threshold
9. WHEN a comment has replies, THE System SHALL display the reply count and provide an option to view replies
10. WHEN a user replies to a comment, THE System SHALL store the reply with a reference to the parent comment

### Requirement 6: User Profile and History

**User Story:** As a user, I want to view my profile statistics and browse my confession and comment history, so that I can track my engagement and contributions to the community.

#### Acceptance Criteria

1. WHEN a user sends the /profile command, THE System SHALL display the user's total approved confessions, total comments, impact points, and community acceptance score
2. WHEN a user sends the /myconfessions command, THE System SHALL display a paginated list of the user's confessions with their status (pending, approved, rejected)
3. WHEN a user sends the /mycomments command, THE System SHALL display a paginated list of the user's comments with context showing the confession they commented on
4. WHEN calculating impact points, THE System SHALL sum the user's approved confessions, comments, and positive reactions received
5. WHEN calculating community acceptance score, THE System SHALL compute the ratio of positive reactions to total reactions across the user's content

### Requirement 7: Database Support and Reliability

**User Story:** As a system administrator, I want the bot to reliably store data in PostgreSQL on Vercel (via Supabase), so that the system is robust and production-ready.

#### Acceptance Criteria

1. WHEN the System starts, THE System SHALL connect to the PostgreSQL database using the configured Supabase connection credentials
2. WHEN a database connection fails, THE System SHALL retry the connection up to three times with exponential backoff
3. WHEN the database connection URL contains special characters in the password, THE System SHALL properly handle the connection
4. WHEN the System performs database operations, THE System SHALL use Django's connection pooling to manage database connections efficiently
5. WHEN a database transaction fails, THE System SHALL roll back the transaction and log the error
6. WHEN the System deploys on Vercel, THE System SHALL run all pending database migrations automatically via the build script

### Requirement 8: Database Security and Access Control

**User Story:** As a system administrator, I want all database tables to have proper Row Level Security (RLS) enabled, so that unauthorized direct database access is prevented and data is protected from security vulnerabilities.

#### Acceptance Criteria

1. WHEN the System creates any database table, THE System SHALL enable Row Level Security (RLS) on that table
2. WHEN RLS is enabled on a table, THE System SHALL create policies that allow full access for the authenticated service role
3. WHEN RLS is enabled on a table, THE System SHALL create policies that deny direct public access to anonymous users
4. WHEN the bot_feedback table exists, THE System SHALL have RLS enabled with appropriate access policies
5. WHEN the bot_user table exists, THE System SHALL have RLS enabled with appropriate access policies
6. WHEN the bot_confession table exists, THE System SHALL have RLS enabled with appropriate access policies
7. WHEN the bot_comment table exists, THE System SHALL have RLS enabled with appropriate access policies
8. WHEN the bot_reaction table exists, THE System SHALL have RLS enabled with appropriate access policies
9. WHEN Django system tables exist, THE System SHALL have RLS enabled with appropriate access policies

### Requirement 9: Error Handling and User Feedback

**User Story:** As a user, I want to receive clear feedback when I interact with the bot, so that I understand the results of my actions and can correct any errors.

#### Acceptance Criteria

1. WHEN a user sends an invalid command, THE System SHALL respond with a helpful error message and suggest valid commands
2. WHEN a user attempts to comment on a non-existent confession, THE System SHALL inform the user that the confession ID is invalid
3. WHEN a user attempts to perform an admin action without admin privileges, THE System SHALL inform the user that they lack the required permissions
4. WHEN a database error occurs, THE System SHALL log the error details and inform the user that a temporary issue occurred
5. WHEN a user submits a confession successfully, THE System SHALL confirm the submission and inform the user that it is pending review
