
const session=EdgeAuth.current(),u=EdgeDB.users.find(x=>x.id===session.id);
document.getElementById("setting-name").value=u.nome;document.getElementById("setting-email").value=u.email;
document.getElementById("theme").value=localStorage.getItem("edge_theme")||"light";document.getElementById("font-size").value=localStorage.getItem("edge_font")||"normal";
document.getElementById("save-account").onclick=()=>{u.nome=document.getElementById("setting-name").value.trim()||u.nome;u.email=document.getElementById("setting-email").value.trim()||u.email;EdgeDB.save();showToast("Dados da conta salvos.")};
document.getElementById("save-appearance").onclick=()=>{localStorage.setItem("edge_theme",document.getElementById("theme").value);localStorage.setItem("edge_font",document.getElementById("font-size").value);document.body.classList.toggle("dark",document.getElementById("theme").value==="dark");document.body.classList.toggle("large",document.getElementById("font-size").value==="large");showToast("Preferências salvas.")};
if(session.cargo==="administrador"){document.getElementById("save-system").onclick=()=>showToast("Configurações do sistema salvas no modo demonstração.")}else{document.querySelector(".admin-only")?.remove()}
