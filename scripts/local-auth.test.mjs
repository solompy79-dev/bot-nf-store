import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { localAuthPlugin } from "./local-auth.mjs";

test("local accounts: sessions, isolation, CSRF, persistence and password rotation", async () => {
 const directory = mkdtempSync(join(tmpdir(), "ishtiraki-auth-"));
 const previous = { mode: process.env.LOCAL_AUTH, db: process.env.LOCAL_AUTH_DB };
 process.env.LOCAL_AUTH="true"; process.env.LOCAL_AUTH_DB=join(directory,"accounts.sqlite");
 let middleware;
 const server=createServer((req,res)=>middleware(req,res,()=>{res.statusCode=404;res.end()}));
 localAuthPlugin().configureServer({httpServer:server,middlewares:{use:fn=>{middleware=fn}}});
 await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
 const origin="http://127.0.0.1:"+server.address().port;
 const request=async(action,body,cookie="",trusted=true)=>{
  const response=await fetch(origin+"/api/local-auth/"+action,{method:body===undefined?"GET":"POST",headers:{...(body===undefined?{}:{"Content-Type":"application/json",Origin:trusted?origin:"http://other.example"}),Cookie:cookie},...(body===undefined?{}:{body:JSON.stringify(body)})});
  return {response,data:await response.json()};
 };
 try {
  assert.equal((await request("profile")).response.status,401);
  assert.equal((await request("signup",{email:"x@example.com",password:"Strong-Password-123",full_name:"Test"},"",false)).response.status,403);
  const first=await request("signup",{email:"First@example.com",password:"Strong-Password-123",full_name:"First",phone:""});
  assert.equal(first.response.status,200);
  assert.equal(first.data.user.email,"first@example.com");
  assert.equal(first.data.session.user.id,first.data.user.id);
  const header=first.response.headers.get("set-cookie");
  assert.match(header,/HttpOnly/); assert.match(header,/SameSite=Strict/);
  const cookie=header.split(";")[0];
  assert.equal((await request("session",undefined,cookie)).data.session.user.id,first.data.user.id);
  assert.equal((await request("signin",{email:"first@example.com",password:"Wrong-Password-123"})).response.status,401);
  assert.equal((await request("signup",{email:"first@example.com",password:"Strong-Password-123",full_name:"Again"})).response.status,409);
  const second=await request("signup",{email:"second@example.com",password:"Strong-Password-123",full_name:"Second"});
  const secondCookie=second.response.headers.get("set-cookie").split(";")[0];
  await request("profile",{full_name:"Updated",phone:""},cookie);
  assert.equal((await request("profile",undefined,cookie)).data.full_name,"Updated");
  assert.equal((await request("profile",undefined,secondCookie)).data.full_name,"Second");
  assert.equal((await request("password",{password:"New-Password-456",current_password:"wrong"},cookie)).response.status,403);
  const changed=await request("password",{password:"New-Password-456",current_password:"Strong-Password-123"},cookie);
  assert.equal(changed.response.status,200);
  assert.equal((await request("session",undefined,cookie)).data.session,null);
  const newCookie=changed.response.headers.get("set-cookie").split(";")[0];
  await request("signout",{},newCookie);
  assert.equal((await request("session",undefined,newCookie)).data.session,null);
  assert.equal((await request("signin",{email:"first@example.com",password:"Strong-Password-123"})).response.status,401);
  assert.equal((await request("signin",{email:"first@example.com",password:"New-Password-456"})).response.status,200);
 } finally {
  await new Promise(resolve=>server.close(resolve));
  if(previous.mode===undefined)delete process.env.LOCAL_AUTH;else process.env.LOCAL_AUTH=previous.mode;
  if(previous.db===undefined)delete process.env.LOCAL_AUTH_DB;else process.env.LOCAL_AUTH_DB=previous.db;
  rmSync(directory,{recursive:true,force:true});
 }
});
