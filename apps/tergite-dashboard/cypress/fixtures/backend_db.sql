-- TABLE (RE)CREATION
DROP TABLE IF EXISTS user;
CREATE TABLE user (
	id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	email VARCHAR NOT NULL, 
	password VARCHAR NOT NULL, 
	is_admin BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_user_email ON user (email);
CREATE INDEX ix_user_id ON user (id);

DROP TABLE IF EXISTS booking;
CREATE TABLE booking (
	id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	start_utc DATETIME NOT NULL, 
	end_utc DATETIME NOT NULL, 
	start_event_id VARCHAR NOT NULL, 
	end_event_id VARCHAR NOT NULL, 
	idle_timer_id VARCHAR NOT NULL, 
	total_duration FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE SET NULL
);

CREATE INDEX ix_booking_start_utc ON booking (start_utc);
CREATE INDEX ix_booking_user_id ON booking (user_id);
CREATE INDEX ix_booking_end_utc ON booking (end_utc);
CREATE INDEX ix_booking_id ON booking (id);

-- SEED DATA

INSERT INTO "user" (id,name,email,password,is_admin) VALUES
	 ('5ddc8d9fb69602723cd3c38f','jane.doe','jane.doe@example.com','some-password',false),
	 ('40fbb5de7422a04fabd8d22a','paul.doe','paul.doe@example.com','some-password',false),
	 ('858877267fe722a38619fa2e','david.doe','david.doe@example.com','some-password',false),
	 ('4939a0b9a7742e2cc52289e0','john.doe','john.doe@example.com','some-password',false),
	 ('0558648bbf51b16948e818d3','julie.doe','julie.doe@example.com','some-password',false);

INSERT INTO booking (id,user_id,start_utc,end_utc,start_event_id,end_event_id,idle_timer_id,total_duration) VALUES
	 ('9dbfd214-454f-4e4a-bf65-b8906ef9eac7','5ddc8d9fb69602723cd3c38f','2025-10-01T00:10:00.000Z','2025-10-01T01:00:00.000Z','','','',3000.0),
	 ('950a9046-15c3-407c-a6b3-5c3ba81b93fe','5ddc8d9fb69602723cd3c38f','2025-10-01T01:00:00.000Z','2025-10-01T01:30:00.000Z','','','',1800.0),
	 ('20816fc4-6c94-446b-bdd8-7ef588590ee3','5ddc8d9fb69602723cd3c38f','2025-10-01T01:30:00.000Z','2025-10-01T01:50:00.000Z','','','',1200.0),
	 ('54dbdcb0-5ff3-406b-9051-834f7fd4f604','5ddc8d9fb69602723cd3c38f','2025-10-01T01:50:00.000Z','2025-10-01T02:50:00.000Z','','','',3600.0),
	 ('23581827-3610-410f-8002-6cba9dface89','5ddc8d9fb69602723cd3c38f','2025-10-01T22:00:00.000Z','2025-10-01T23:30:00.000Z','','','',5400.0),
	 ('cb60a8fc-ff1e-4c76-94d4-bad1e50355a8','5ddc8d9fb69602723cd3c38f','2025-10-03T00:00:00.000Z','2025-10-03T02:00:00.000Z','','','',7200.0),
	 ('2807492d-1097-493a-a0c2-4c0f5e24e9c6','5ddc8d9fb69602723cd3c38f','2025-10-02T04:00:00.000Z','2025-10-02T04:30:00.000Z','','','',1800.0),
	 ('42609964-b433-4387-98e5-5ad5d41823aa','5ddc8d9fb69602723cd3c38f','2025-09-30T02:00:00.000Z','2025-09-30T03:30:00.000Z','','','',5400.0),
	 ('a4bbd31f-f183-47ed-aeb5-3b10e8c87cf5','5ddc8d9fb69602723cd3c38f','2025-09-29T00:00:00.000Z','2025-09-29T02:00:00.000Z','','','',7200.0);
