// collide_check.cpp —— AG-1 收起姿态穿模检测（Bullet GImpact 精确三角网格）
// 读 ag1_collide.bin，每个零件建 btGImpactMeshShape，放进 btCollisionWorld 求交
// 只报告 "gear* vs 非 gear*"，并按穿透深度排序

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <algorithm>

#include "btBulletCollisionCommon.h"
#include "BulletCollision/Gimpact/btGImpactCollisionAlgorithm.h"
#include "BulletCollision/Gimpact/btGImpactShape.h"

struct Part {
    std::string name, role;
    btGImpactMeshShape* shape = nullptr;
    btCollisionObject* obj = nullptr;
};

static std::vector<Part> loadParts(const char* path,
                                   btTriangleMesh** keepMesh,
                                   std::vector<btTriangleMesh*>& meshes) {
    std::vector<Part> out;
    FILE* f = fopen(path, "rb");
    if (!f) { printf("cannot open %s\n", path); exit(1); }
    char magic[4]; fread(magic, 1, 4, f);
    if (memcmp(magic, "AG1C", 4)) { printf("bad magic\n"); exit(1); }
    unsigned int n = 0; fread(&n, 4, 1, f);
    for (unsigned int i = 0; i < n; i++) {
        unsigned int nl = 0; fread(&nl, 4, 1, f);
        std::string nm(nl, 0); fread(&nm[0], 1, nl, f);
        unsigned int rl = 0; fread(&rl, 4, 1, f);
        std::string rl_s(rl, 0); fread(&rl_s[0], 1, rl, f);
        unsigned int vc = 0; fread(&vc, 4, 1, f);
        std::vector<float> v(vc * 3); fread(v.data(), 4, vc * 3, f);
        unsigned int ic = 0; fread(&ic, 4, 1, f);
        std::vector<unsigned int> idx(ic); fread(idx.data(), 4, ic, f);

        btTriangleMesh* tm = new btTriangleMesh();
        for (unsigned int k = 0; k + 2 < ic; k += 3) {
            btVector3 a(v[idx[k] * 3], v[idx[k] * 3 + 1], v[idx[k] * 3 + 2]);
            btVector3 b(v[idx[k + 1] * 3], v[idx[k + 1] * 3 + 1], v[idx[k + 1] * 3 + 2]);
            btVector3 c(v[idx[k + 2] * 3], v[idx[k + 2] * 3 + 1], v[idx[k + 2] * 3 + 2]);
            tm->addTriangle(a, b, c);
        }
        meshes.push_back(tm);

        Part p;
        p.name = nm; p.role = rl_s;
        p.shape = new btGImpactMeshShape(tm);
        p.shape->setMargin(0.0f);
        p.shape->updateBound();

        p.obj = new btCollisionObject();
        p.obj->setCollisionShape(p.shape);
        p.obj->setUserIndex((int)out.size());
        out.push_back(p);
    }
    fclose(f);
    return out;
}

int main(int argc, char** argv) {
    const char* bin = (argc > 1) ? argv[1] : "ag1_collide.bin";

    btDefaultCollisionConfiguration cfg;
    btCollisionDispatcher disp(&cfg);
    btGImpactCollisionAlgorithm::registerAlgorithm(&disp);
    btDbvtBroadphase bp;
    btCollisionWorld world(&disp, &bp, &cfg);

    std::vector<btTriangleMesh*> meshes;
    std::vector<Part> parts = loadParts(bin, nullptr, meshes);
    printf("loaded %zu parts\n", parts.size());

    for (auto& p : parts) world.addCollisionObject(p.obj);
    world.performDiscreteCollisionDetection();

    struct Hit { float depth; std::string a, b; btVector3 pos; };
    std::vector<Hit> hits;
    int totalManifolds = 0;

    int nm = disp.getNumManifolds();
    for (int i = 0; i < nm; i++) {
        btPersistentManifold* m = disp.getManifoldByIndexInternal(i);
        const btCollisionObject* o0 = m->getBody0();
        const btCollisionObject* o1 = m->getBody1();
        const Part& p0 = parts[o0->getUserIndex()];
        const Part& p1 = parts[o1->getUserIndex()];

        bool g0 = (p0.role == "gear"), g1 = (p1.role == "gear");
        if (g0 == g1) continue;          // 两边同为齿轮或同非齿轮 → 跳过
        totalManifolds++;

        float worst = 0.0f; btVector3 wp(0, 0, 0);
        for (int c = 0; c < m->getNumContacts(); c++) {
            const btManifoldPoint& pt = m->getContactPoint(c);
            float d = pt.getDistance();
            if (d < worst) { worst = d; wp = pt.getPositionWorldOnA(); }
        }
        if (worst < -0.001f) {           // 只报真穿透 > 1mm
            Hit h;
            h.depth = -worst;
            h.a = g0 ? p0.name : p1.name;
            h.b = g0 ? p1.name : p0.name;
            h.pos = wp;
            hits.push_back(h);
        }
    }

    std::sort(hits.begin(), hits.end(),
              [](const Hit& x, const Hit& y) { return x.depth > y.depth; });

    printf("gear-vs-equip manifolds: %d\n", totalManifolds);
    printf("=== REAL PENETRATIONS (>1mm): %zu ===\n", hits.size());
    for (auto& h : hits)
        printf("  %-22s <-> %-22s  depth=%6.1fmm  at(%.2f,%.2f,%.2f)\n",
               h.a.c_str(), h.b.c_str(), h.depth * 1000.0f,
               h.pos.x(), h.pos.y(), h.pos.z());

    return 0;
}
