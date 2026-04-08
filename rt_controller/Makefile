CC = gcc
CFLAGS = -Wall -Wextra -O2 -std=c99
LDFLAGS = -lmosquitto -lpthread -lrt
TARGET = greenhouse_controller

SOURCES = greenhouse_controller.c
OBJECTS = $(SOURCES:.c=.o)

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $<

clean:
	rm -f $(OBJECTS) $(TARGET)

run: $(TARGET)
	./$(TARGET)

.PHONY: all clean run
