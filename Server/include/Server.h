#ifndef SERVER_H
#define SERVER_H
#ifdef _WIN32
#ifdef DMNET
#define DMNET __declspec(dllexport)
#else
#define DMNET __declspec(dllimport)
#endif
#else
#define DMNET
#endif
class DMNET Server {
public:
	Server(int port);
private:
	void initialize();
	void cleanup();
};
#endif