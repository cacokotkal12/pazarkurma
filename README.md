# pazarkurma
pazar kurmak için makro

## PR oluşturma notları

Depodaki değişiklikleri PR olarak açabilmek için aşağıdaki adımları takip edin:

1. Dosyalarda yaptığınız düzenlemeleri `git add` ile sahneleyin.
2. Değişiklikleri açıklayan bir mesajla commit oluşturun (`git commit -m "Mesaj"`).
3. Uzak depo ekli değilse `git remote add origin <repo-url>` komutuyla bir origin tanımlayın.
4. Çalıştığınız dalı uzağa gönderin (`git push -u origin <dal-adi>`).
5. Git sağlayıcınızın arayüzünden PR açın. Bu ortamda otomatik PR oluşturma aracı kullanıyorsanız commit sonrası PR komutunu çalıştırmanız gerekir; commit olmadığında PR oluşmaz.

### “PR oluşturulamadı” hatasını çözmek için hızlı kontrol listesi

Bu hatayı görmeye devam ediyorsanız aşağıdaki maddeleri sırayla doğrulayın:

1. **Staged + commit var mı?** `git status` ile çalışma alanının temiz olduğunu ve en az bir commit bulunduğunu kontrol edin. Değişiklikler commit edilmediyse PR açılmaz.
2. **Uzak depo tanımlandı mı?** `git remote -v` komutunda `origin` görünmüyorsa `git remote add origin <repo-url>` ile ekleyin.
3. **Dal pushlandı mı?** `git push -u origin <dal-adi>` komutunu çalıştırmadan GitHub/GitLab PR sayfası dalı görmez.
4. **Doğru daldasınız.** PR oluşturmak istediğiniz dalın adını `git branch --show-current` ile kontrol edin; gerekirse o dala geçin.
5. **Yetki sorunu var mı?** Uzak depoya yazma izniniz yoksa push başarısız olur; yetki olmadığında forka push edip PR’ı fork üzerinden açın.
6. **Otomatik araç kullanıyorsanız**: Commit ve push tamamlandıktan sonra PR komutunu tekrar çalıştırın; commit yoksa araç PR üretmez.

Her adımdan sonra hata devam ederse komutların çıktısını inceleyin; çoğu zaman eksik commit veya push işlemi sorunu çözer.
