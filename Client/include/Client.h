#ifndef CLIENT_H
#define CLIENT_H
#ifdef _WIN32
#ifdef DMNET
#define DMNET __declspec(dllexport)
#else
#define DMNET __declspec(dllimport)
#endif
#else
#define DMNET
#endif
class DMNET Client {
public:
	Client(char* server_ip, int port);
private:
	void initialize();
	void cleanup();
};
#endif