create table users
	(user_id integer PRIMARY KEY,
	 username varchar(30),
	 password varchar(50), 
	first_name varchar(30),
	 last_name varchar(30),
	active integer,
     	profile_picture blob,
	email varchar(30),
     date_joined timestamp);
