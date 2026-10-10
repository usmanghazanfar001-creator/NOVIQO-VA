CREATE TABLE users (
	id VARCHAR(32) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE calendar_accounts (
	user_id VARCHAR(32) NOT NULL, 
	refresh_token VARCHAR(500) NOT NULL, 
	connected_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE conversations (
	id VARCHAR(32) NOT NULL, 
	user_id VARCHAR(32) NOT NULL, 
	title VARCHAR(60) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_conversations_updated_at ON conversations (updated_at);
CREATE INDEX ix_conversations_user_id ON conversations (user_id);

CREATE TABLE memories (
	id SERIAL NOT NULL, 
	user_id VARCHAR(32) NOT NULL, 
	text VARCHAR(200) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_memories_user_id ON memories (user_id);

CREATE TABLE notes (
	id SERIAL NOT NULL, 
	user_id VARCHAR(32) NOT NULL, 
	text TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_notes_user_id ON notes (user_id);

CREATE TABLE password_resets (
	id SERIAL NOT NULL, 
	user_id VARCHAR(32) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	used BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_password_resets_token_hash ON password_resets (token_hash);
CREATE INDEX ix_password_resets_user_id ON password_resets (user_id);

CREATE TABLE reminders (
	id SERIAL NOT NULL, 
	user_id VARCHAR(32) NOT NULL, 
	text VARCHAR(200) NOT NULL, 
	due_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	delivered BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_reminders_due_at ON reminders (due_at);
CREATE INDEX ix_reminders_user_id ON reminders (user_id);

CREATE TABLE user_settings (
	user_id VARCHAR(32) NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE messages (
	id SERIAL NOT NULL, 
	conversation_id VARCHAR(32) NOT NULL, 
	role VARCHAR(9) NOT NULL, 
	content TEXT NOT NULL, 
	via VARCHAR(5) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id)
);
CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

