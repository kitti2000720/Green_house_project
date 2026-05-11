CC      = gcc
CFLAGS  = -Wall -Wextra -O2 -std=c99 -D_POSIX_C_SOURCE=200112L
LDFLAGS = -lmosquitto -lpthread -lrt
TARGET  = greenhouse_controller

SOURCES = greenhouse_controller.c \
          mqtt_handler.c          \
          rules.c                 \
          rt_scheduler.c

OBJECTS = $(SOURCES:.c=.o)

# ------------------------------------------------------------------ #

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

%.o: %.c mqtt_handler.h rules.h
	$(CC) $(CFLAGS) -c $<

clean:
	rm -f $(OBJECTS) $(TARGET)

run: $(TARGET)
	./$(TARGET)

.PHONY: all clean run
