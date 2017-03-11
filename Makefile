#Makefile for compilations
all:
	@clear
	$(MAKE) -C /home/local/twin/kshitiz/coverage/bin covgen

test:
	@clear
	$(MAKE) -C /home/local/twin/kshitiz/coverage/bin test

decode:
	@clear
	$(MAKE) -C /home/local/twin/kshitiz/coverage/bin decode

data:
	$(MAKE) -C bin data

run:
	@echo "Run the executables"

clean:
	$(MAKE) -C bin clean
