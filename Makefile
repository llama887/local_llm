run: server/server.go
	chmod +x cgi/*
	@response=$$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:1234/v1/models/); \
	if [ $$response -eq 200 ]; then \
		echo "Lm Studio Running on Port 1234"; \
		chmod +x cgi/* && cd server && go run server.go \
	else \
		echo "Lm Studio not Running on Port 1234, please start the server"; \
		exit 1; \
	fi

install: requirements.txt
	pip install uv && uv pip install -r requirements.txt

clean: scripts/delete_jinja_generated.sh
	# rm -rf bin
	@chmod +x scripts/delete_jinja_generated.sh && ./scripts/delete_jinja_generated.sh