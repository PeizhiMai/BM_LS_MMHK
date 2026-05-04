#include <cassert>
#include <iostream>
#include <iomanip>
#include "qbasis.h"
#include <cmath>
#include <fstream>
#include <cstdlib>  // For std::atoi

#define PI 3.1415926535897932

// Fermi-Hubbard model on square lattice
int main(int argc, char *argv[]) {
    // Check if at least two arguments are provided (not counting the program name)
    if (argc < 7) {
        std::cerr << "Usage: " << argv[0] << "N_up N_dn <kx> <ky> qx qy" << std::endl;
        return 1;
    }

    // Read the first two command-line arguments into kx and ky
    int Nupinput = std::atoi(argv[1]);
    int Ndninput = std::atoi(argv[2]);
    int kx = std::atoi(argv[3]);  // Convert the first argument to an integer
    int ky = std::atoi(argv[4]);  // Convert the second argument to an integer
    int Qm = std::atoi(argv[5]);  // Convert the third argument to an integer
    int Qn = std::atoi(argv[6]);  // Convert the fourth argument to an integer

    qbasis::initialize();
    std::cout << std::setprecision(10);
    // parameters
    double t = 1;
    double tp = 0.0;
    double U = 6;
    int Lx = 4;
    int Ly = 4;
    double Nup_total = 1.0*Nupinput;
    double Ndn_total = 1.0*Ndninput;

    double fx = kx * PI/40+0.00001;
    double fy = ky * PI/40+0.00001;
    double sx = sin(fx);
    double cx = cos(fx);
    double sy = sin(fy);
    double cy = cos(fy);
    double cxpy = cos(fx+fy);
    double sxpy = sin(fx+fy);
    double cxmy = cos(fx-fy);
    double sxmy = sin(fx-fy);

    //int step = 150;

    std::cout << "Lx =      " << Lx << std::endl;
    std::cout << "Ly =      " << Ly << std::endl;
    std::cout << "t =       " << t << std::endl;
    std::cout << "U =       " << U << std::endl;
    std::cout << "N_up =    " << Nup_total << std::endl;
    std::cout << "N_dn =    " << Ndn_total << std::endl << std::endl;

    // lattice object
    std::vector<std::string> bc{"pbc", "pbc"};
    qbasis::lattice lattice("square",{static_cast<uint32_t>(Lx), static_cast<uint32_t>(Ly)},bc);


    // local matrix representation
    auto c_up = std::vector<std::vector<std::complex<double>>>(4,std::vector<std::complex<double>>(4, 0.0));
    auto c_dn = std::vector<std::vector<std::complex<double>>>(4,std::vector<std::complex<double>>(4, 0.0));
    c_up[0][1] = std::complex<double>(1.0,0.0);
    c_up[2][3] = std::complex<double>(1.0,0.0);
    c_dn[0][2] = std::complex<double>(1.0,0.0);
    c_dn[1][3] = std::complex<double>(-1.0,0.0);


    // constructing the Hamiltonian in operator representation
    qbasis::model<std::complex<double>> Hubbard(lattice);
    Hubbard.add_orbital(lattice.Nsites, "electron");
    qbasis::mopr<std::complex<double>> Nup;   // an operator representating total electron number
    qbasis::mopr<std::complex<double>> Ndown;
    for (int x = 0; x < Lx; x++) {
        for (int y = 0; y < Ly; y++) {
            uint32_t site_i, site_j;
            std::vector<int> work(lattice.dim);
            lattice.coor2site({x,y}, 0, site_i, work); // obtain site label of (x,y)
            // construct operators on each site
            auto c_up_i    = qbasis::opr<std::complex<double>>(site_i,0,true,c_up);
            auto c_dn_i    = qbasis::opr<std::complex<double>>(site_i,0,true,c_dn);
            auto c_up_dg_i = c_up_i; c_up_dg_i.dagger();
            auto c_dn_dg_i = c_dn_i; c_dn_dg_i.dagger();
            auto n_up_i    = c_up_dg_i * c_up_i;
            auto n_dn_i    = c_dn_dg_i * c_dn_i;

            // hopping to neighbor (x+1, y)
            if (bc[0] == "pbc" || (bc[0] == "obc" && x < Lx - 1)) {
                lattice.coor2site({x+1,y}, 0, site_j, work);
                auto c_up_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
                auto c_dn_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
                auto c_up_dg_j = c_up_j; c_up_dg_j.dagger();
                auto c_dn_dg_j = c_dn_j; c_dn_dg_j.dagger();
                Hubbard.add_Ham(std::complex<double>(-t*cx,-t*sx) * ( c_up_dg_i * c_up_j ));
                Hubbard.add_Ham(std::complex<double>(-t*cx,t*sx ) * ( c_up_dg_j * c_up_i ));
                Hubbard.add_Ham(std::complex<double>(-t*cx,-t*sx) * ( c_dn_dg_i * c_dn_j ));
                Hubbard.add_Ham(std::complex<double>(-t*cx,t*sx ) * ( c_dn_dg_j * c_dn_i ));
            }

            // hopping to neighbor (x, y+1)
            if (bc[1] == "pbc" || (bc[1] == "obc" && y < Ly - 1)) {
                lattice.coor2site({x,y+1}, 0, site_j, work);
                auto c_up_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
                auto c_dn_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
                auto c_up_dg_j = c_up_j; c_up_dg_j.dagger();
                auto c_dn_dg_j = c_dn_j; c_dn_dg_j.dagger();
                Hubbard.add_Ham(std::complex<double>(-t*cy,-t*sy) * ( c_up_dg_i * c_up_j ));
                Hubbard.add_Ham(std::complex<double>(-t*cy,t*sy ) * ( c_up_dg_j * c_up_i ));
                Hubbard.add_Ham(std::complex<double>(-t*cy,-t*sy) * ( c_dn_dg_i * c_dn_j ));
                Hubbard.add_Ham(std::complex<double>(-t*cy,t*sy ) * ( c_dn_dg_j * c_dn_i ));
            }

            // hopping to second neighbor (x+1, y+1)
            if (bc[0] == "pbc" || (bc[0] == "obc" && x < Lx - 1 && y < Ly - 1)) {
                lattice.coor2site({x+1,y+1}, 0, site_j, work);
                auto c_up_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
                auto c_dn_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
                auto c_up_dg_j = c_up_j; c_up_dg_j.dagger();
                auto c_dn_dg_j = c_dn_j; c_dn_dg_j.dagger();
                Hubbard.add_Ham(std::complex<double>(-tp*cxpy,-tp*sxpy) * ( c_up_dg_i * c_up_j ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxpy,tp*sxpy ) * ( c_up_dg_j * c_up_i ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxpy,-tp*sxpy) * ( c_dn_dg_i * c_dn_j ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxpy,tp*sxpy ) * ( c_dn_dg_j * c_dn_i ));
            }

            if (bc[0] == "pbc" || (bc[0] == "obc" && x < Lx - 1 && y < Ly - 1 && y > 0)) {
                lattice.coor2site({x+1,y-1}, 0, site_j, work);
                auto c_up_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
                auto c_dn_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
                auto c_up_dg_j = c_up_j; c_up_dg_j.dagger();
                auto c_dn_dg_j = c_dn_j; c_dn_dg_j.dagger();
                Hubbard.add_Ham(std::complex<double>(-tp*cxmy,-tp*sxmy) * ( c_up_dg_i * c_up_j ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxmy,tp*sxmy ) * ( c_up_dg_j * c_up_i ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxmy,-tp*sxmy) * ( c_dn_dg_i * c_dn_j ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxmy,tp*sxmy ) * ( c_dn_dg_j * c_dn_i ));
            }

            // Hubbard repulsion, note that this operator is a sum (over sites) of diagonal matrices
            Hubbard.add_Ham(std::complex<double>(U,0.0) * (n_up_i * n_dn_i));

            // total electron operator
            Nup   += n_up_i;
            Ndown += n_dn_i;
        }
    }


    // to use translational symmetry, we first fill the Weisse tables
    Hubbard.fill_Weisse_table();


    // measure operators

    std::vector<double> E0_list;
    for (int m = 0; m < 1; m++) {
        for (int n = 0; n < 1; n++) {
            
            // constructing the Hilbert space basis
            Hubbard.enumerate_basis_repr({Qm,Qn}, {Nup,Ndown}, {Nup_total,Ndn_total});

            // generating matrix of the Hamiltonian in the subspace
            Hubbard.generate_Ham_sparse_repr();
            std::cout << std::endl;

            // obtaining the lowest eigenvals of the matrix
            Hubbard.locate_E0_lanczos(qbasis::which_sym::repr);
            std::cout << std::endl;

            E0_list.push_back(Hubbard.eigenvals_repr[0]);

            
        }
    }

    // prepare list of momentum points for measurement
    std::vector<std::vector<int>> q_list;
    // along q in the upper triangle
    //for (int m = 0; m <= Lx/2; m++) {
    //    for (int n = 0; n <= Ly/2; n++) {
    for (int m = 0; m < 1; m++) {
        for (int n = 0; n < 1; n++) {
            q_list.push_back({m,n});
        }
    }
    //std::cout << "q_list = " << q_list << std::endl;

    // calculate single-particle Green function G(q,w)
    std::string output_name_p = "L"+std::to_string(Lx)+"x"+std::to_string(Ly)+"Nup"+std::to_string(int(Nup_total))+"Ndn"+std::to_string(int(Ndn_total))+"f"+std::to_string(kx)+"x"+std::to_string(ky)+"Q"+std::to_string(Qm)+"x"+std::to_string(Qn)+"_obs.dat";
    std::ofstream fout_p(output_name_p, std::ios::out);
    fout_p << std::scientific << std::right;
    fout_p << std::setprecision(18);
    fout_p << "Lx\t" << Lx << std::endl;
    fout_p << "Ly\t" << Ly << std::endl;
    fout_p << "U\t" << U << std::endl;
    fout_p << "E0\t" << Hubbard.energy_min() << std::endl;
    fout_p << "Gap\t" << Hubbard.energy_gap() << std::endl << std::endl;


    // loop over all the q points
    for (auto q : q_list) {
        int m = q[0];
        int n = q[1];
        std::cout << "k\t" << m << "," << n << std::endl;
        fout_p << "Q\t" << m << "," << n << std::endl;

        // construct c_up(q) and c_up^\dagger(q)
        qbasis::mopr<std::complex<double>> c_up_q, c_up_dg_q, c_dn_q, c_dn_dg_q, n_up_q, n_dn_q, n_q, n_q2;
	qbasis::mopr<std::complex<double>> n_up_i_spe, n_dn_i_spe;
        std::complex<double> m1 = 0, m2 = 0, m3 = 0;

        for (int x = 0; x < Lx; x++) {
            for (int y = 0; y < Ly; y++) {
                double qdotr = 2.0 * PI * (m * x / static_cast<double>(Lx) + n * y / static_cast<double>(Ly));
                auto coeff = 1.0 / sqrt(static_cast<double>(Lx * Ly)) * std::exp(std::complex<double>{0.0,qdotr});
                auto coeffm = 1.0 / sqrt(static_cast<double>(Lx * Ly)) * std::exp(std::complex<double>{0.0,-qdotr});
                uint32_t site;
                std::vector<int> work(lattice.dim);
                lattice.coor2site({x,y}, 0, site, work);
                auto c_up_i    = qbasis::opr<std::complex<double>>(site,0,true,c_up);
                auto c_up_dg_i = c_up_i; c_up_dg_i.dagger();
                c_up_q += coeff * c_up_i;
                c_up_dg_q += coeffm * c_up_dg_i;
                
                auto c_dn_i    = qbasis::opr<std::complex<double>>(site,0,true,c_dn);
                auto c_dn_dg_i = c_dn_i; c_dn_dg_i.dagger();
                c_dn_q += coeff * c_dn_i;
                c_dn_dg_q += coeffm * c_dn_dg_i;


	        n_up_i_spe += c_up_dg_i * c_up_i * c_dn_dg_i * c_dn_i;
		n_dn_i_spe += (c_dn_dg_i * c_dn_i + c_up_dg_i * c_up_i);
                
            }
        }
        c_up_q.simplify();
        c_up_dg_q.simplify();
        Hubbard.enumerate_basis_repr({Qm-m,Qn-n}, {Nup,Ndown}, {Nup_total-1,Ndn_total},1);
        std::vector<std::complex<double>> vec_newcup(Hubbard.dim_repr[1]);
        MKL_INT which_col = 0;
        Hubbard.moprXvec_repr(c_up_q, 0, 1, which_col, vec_newcup.data());
        
        c_dn_q.simplify();
        c_dn_dg_q.simplify();
        Hubbard.enumerate_basis_repr({Qm-m,Qn-n}, {Nup,Ndown}, {Nup_total,Ndn_total-1},2);
        std::vector<std::complex<double>> vec_newcdn(Hubbard.dim_repr[2]);
        Hubbard.moprXvec_repr(c_dn_q, 0, 2, which_col, vec_newcdn.data());

        
        n_up_q = c_up_dg_q * c_up_q;
        n_dn_q = c_dn_dg_q * c_dn_q;
        n_up_q.simplify();
        n_dn_q.simplify();
        std::vector<std::complex<double>> vec_newnup(Hubbard.dim_repr[0]);
        Hubbard.moprXvec_repr(n_up_q, 0, 0, which_col, vec_newnup.data());
        std::vector<std::complex<double>> vec_newndn(Hubbard.dim_repr[0]);
        Hubbard.moprXvec_repr(n_dn_q, 0, 0, which_col, vec_newndn.data());

        for (int ix = 0; ix < Hubbard.dim_repr[1]; ix++) {
            m1 += std::conj(vec_newcup[ix]) * vec_newcup[ix] + std::conj(vec_newcdn[ix]) * vec_newcdn[ix];
            }
        
        for (int ix = 0; ix < Hubbard.dim_repr[0]; ix++) {
            m2 += std::conj(vec_newnup[ix]) * vec_newndn[ix];
            }

        
        n_up_i_spe.simplify();
        n_dn_i_spe.simplify();
        std::vector<std::complex<double>> vec_newnup_spec(Hubbard.dim_repr[0]);
        Hubbard.moprXvec_repr(n_up_i_spe, 0, 0, which_col, vec_newnup_spec.data());
        std::vector<std::complex<double>> vec_newndn_spec(Hubbard.dim_repr[0]);
        Hubbard.moprXvec_repr(n_dn_i_spe, 0, 0, which_col, vec_newndn_spec.data());

	for (int ix = 0; ix < Hubbard.dim_repr[0]; ix++) {
            m3 += std::conj(vec_newnup_spec[ix]) * vec_newndn_spec[ix] / (1.0*Lx) / (1.0*Ly)/ (Nup_total + Ndn_total);
            }

        //for (int ix = 0; ix < Hubbard.dim_repr[0]; ix++) {
        //    double squared_norm = calculateSquaredNorm(vec_newcup);

        //    m1 += std::conj(vec_newnup.data(1))*
        //}
        //m1 = m1/Hubbard.dim_repr[1];
        //n_q = n_up_q + n_dn_q;
        //n_q2 = n_up_q * n_dn_q;
        //n_q.simplify();
        //n_q2.simplify();

        //m1 = Hubbard.measure_repr_static(n_q, 0, 0);
        fout_p << "<nq> " << std::real(m1) << std::endl;

        //m2 = Hubbard.measure_repr_static(n_q2, 0, 0);
        fout_p << "<nq_upnq_dn> " << std::real(m2) << std::endl;
        std::cout << std::endl;

        //m3 = Hubbard.measure_repr_static(n_i2, 0, 0);
        fout_p << "<ni_upni_dn> " << std::real(m3) << std::endl;
        std::cout << std::endl;

        // calculate <Spipi> using q = (pi, pi) component (same definition as Spipit0 code)
        qbasis::mopr<std::complex<double>> s_pipi;
        int mq = Lx / 2;
        int nq = Ly / 2;
        for (int x = 0; x < Lx; x++) {
            for (int y = 0; y < Ly; y++) {
                double qdotr = 2.0 * PI * (mq * x / static_cast<double>(Lx) + nq * y / static_cast<double>(Ly));
                auto coeff = 0.5 * 1.0 / sqrt(static_cast<double>(Lx * Ly)) * std::exp(std::complex<double>{0.0, qdotr});
                uint32_t site;
                std::vector<int> work(lattice.dim);
                lattice.coor2site({x, y}, 0, site, work);
                auto c_up_i = qbasis::opr<std::complex<double>>(site, 0, true, c_up);
                auto c_up_dg_i = c_up_i; c_up_dg_i.dagger();
                auto c_dn_i = qbasis::opr<std::complex<double>>(site, 0, true, c_dn);
                auto c_dn_dg_i = c_dn_i; c_dn_dg_i.dagger();

                s_pipi += coeff * (c_up_dg_i * c_up_i - c_dn_dg_i * c_dn_i);
            }
        }
        s_pipi.simplify();
        Hubbard.enumerate_basis_repr({mq, nq}, {Nup, Ndown}, {Nup_total, Ndn_total}, 1);
        std::vector<std::complex<double>> vec_spipi(Hubbard.dim_repr[1]);
        Hubbard.moprXvec_repr(s_pipi, 0, 1, which_col, vec_spipi.data());
        std::complex<double> m_spipi = 0;
        for (int ix = 0; ix < Hubbard.dim_repr[1]; ix++) {
            m_spipi += std::conj(vec_spipi[ix]) * vec_spipi[ix];
        }
        fout_p << "<Spipi> " << std::real(m_spipi) << std::endl;
        std::cout << std::endl;

                
    }
    fout_p.close();

}
