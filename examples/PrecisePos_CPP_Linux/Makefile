CPPFLAGS += -std=c++11  -I../../code
LDLIBS   += -ldl -g

# Needed by ForceSeatDI
LDLIBS   += -pthread

OBJ += tmp/cpp/main.o
OBJ += tmp/c/ForceSeatDI_Loader.o

all: | prepare RunMe

$(OBJ): | prepare

RunMe: $(OBJ)
	g++ $(LDFLAGS) $(OBJ) $(LDLIBS) --output $@

tmp/c/%.o: ../../code/%.c
	g++ -c $(CPPFLAGS) $< -o $@

tmp/cpp/%.o: %.cpp
	g++ -c $(CPPFLAGS) $< -o $@

prepare::
	mkdir -p tmp
	mkdir -p tmp/c
	mkdir -p tmp/cpp
